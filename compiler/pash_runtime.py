import cProfile
import os
import argparse
import sys
import pickle
import subprocess
import jsonpickle
import traceback
from datetime import datetime

from ir import *
from ast_to_ir import compile_asts
from json_ast import *
from ir_to_ast import to_shell
from parse import from_ir_to_shell
from util import *
import config

from definitions.ir.nodes.alt_bigram_g_reduce import *
from definitions.ir.nodes.bigram_g_map import *
from definitions.ir.nodes.bigram_g_reduce import *
from definitions.ir.nodes.sort_g_reduce import *
from definitions.ir.nodes.eager import *
from definitions.ir.nodes.pash_split import *

import definitions.ir.nodes.r_merge as r_merge
import definitions.ir.nodes.r_split as r_split
import definitions.ir.nodes.r_unwrap as r_unwrap
import definitions.ir.nodes.dgsh_tee as dgsh_tee


runtime_config = {}
## We want to catch all exceptions here so that they are logged correctly
## and not just printed to the stderr.
def main():
    try:
        main_body()
    except Exception:
        log("Compiler failed, no need to worry, executing original script...")
        log(traceback.format_exc())
        sys.exit(1)

def main_body():
    ## Parse arguments
    args = parse_args()
    config.pash_args = args

    ## Ensure that PASH_TMP_PREFIX is set by pash.py
    assert(not os.getenv('PASH_TMP_PREFIX') is None)
    config.PASH_TMP_PREFIX = os.getenv('PASH_TMP_PREFIX')

    ## Call the main procedure
    compile_optimize_script(args.input_ir, args.compiled_script_file, args)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("compiled_script_file",
                        help="the file in which to output the compiled script")
    parser.add_argument("input_ir",
                        help="the file containing the dataflow graph to be optimized and executed")
    parser.add_argument("--var_file",
                        help="determines the path of a file containing all shell variables.",
                        default=None)
    config.add_common_arguments(parser)
    args = parser.parse_args()
    return args

def compile_optimize_script(ir_filename, compiled_script_file, args):
    global runtime_config
    if not config.config:
        config.load_config(args.config_path)

    ## Load annotations
    config.annotations = load_annotation_files(config.config['distr_planner']['annotations_dir'])

    runtime_config = config.config['distr_planner']

    log("Retrieving candidate DF region: {} ... ".format(ir_filename), end='')
    with open(ir_filename, "rb") as ir_file:
        candidate_df_region = pickle.load(ir_file)
    log("Done!")

    ## Read any shell variables files if present
    config.read_vars_file(args.var_file)

    ## Compile the candidate DF regions
    compilation_start_time = datetime.now()
    asts_and_irs = compile_candidate_df_region(candidate_df_region, config.config)
    compilation_end_time = datetime.now()
    print_time_delta("Compilation", compilation_start_time, compilation_end_time, args)

    ## Optimize all the IRs that can be optimized
    if(args.no_optimize):
        optimized_asts_and_irs = asts_and_irs
    else:
        optimized_asts_and_irs = optimize_irs(asts_and_irs, args)

    ## TODO: Normally this could return more than one compiled ASTs (containing IRs in them).
    ##       To correctly handle that we would need to really replace the optimized IRs
    ##       with the final parallel corresponding scripts.
    ##
    ##       However, for now we just assume that there is one IR that we can execute as is.
    ##
    ## TODO: This might bite us with the quick-abort.
    ##       It might complicate things having a script whose half is compiled to a graph and its other half not.
    assert(len(optimized_asts_and_irs) == 1)
    optimized_ast_or_ir = optimized_asts_and_irs[0]

    ## Call the backend that executes the optimized dataflow graph
    output_script_path = runtime_config['optimized_script_filename']
    ## TODO: Should never be the case for now. This is obsolete.
    assert(not runtime_config['distr_backend'])

    ## If the candidate DF region was indeed a DF region then we have an IR
    ## which should be translated to a parallel script.
    if(isinstance(optimized_ast_or_ir, IR)):
        script_to_execute = to_shell(optimized_ast_or_ir,
                                     runtime_config['output_dir'], args)

        log("Optimized script saved in:", compiled_script_file)

        ## TODO: Merge this write with the one below. Maybe even move this logic in `pash_runtime.sh`
        ## Output the optimized shell script for inspection
        if(args.output_optimized):
            with open(output_script_path, "w") as output_script_file:
                log("Optimized script:")
                log(script_to_execute)
                output_script_file.write(script_to_execute)

        with open(compiled_script_file, "w") as f:
                f.write(script_to_execute)

    else:
        ## Instead of outputing the script here, we just want to exit with a specific exit code
        ## TODO: Figure out the code and save it somewhere
        sys.exit(120)


def compile_candidate_df_region(candidate_df_region, config):
    ## This is for the files in the IR
    fileIdGen = FileIdGen()

    ## If the candidate DF region is not from the top level then
    ## it won't be a list and thus we need to make it into a list to compile it.
    if(not isinstance(candidate_df_region, list)):
        candidate_df_region = [candidate_df_region]

    ## Compile the asts
    ## TODO: Since compilation happens at runtime, we can now expand everything accordingly.
    ##       We can do that using a shell for start:
    ##         if a word is safe to expand, then call a shell to expand it.
    compiled_asts = compile_asts(candidate_df_region, fileIdGen, config)

    return compiled_asts

def optimize_irs(asts_and_irs, args):
    global runtime_config

    optimization_start_time = datetime.now()

    optimized_asts_and_irs = []
    for ast_or_ir in asts_and_irs:
        if(isinstance(ast_or_ir, IR)):
            ## Assert that the graph that was returned from compilation is valid
            assert(ast_or_ir.valid())

            # log(ir_node)
            # with cProfile.Profile() as pr:
            distributed_graph = naive_parallelize_stateless_nodes_bfs(ast_or_ir, args.width,
                                                                      runtime_config['batch_size'],
                                                                      args.no_cat_split_vanish,
                                                                      args.r_split, args.r_split_batch_size)
            # pr.print_stats()
            # log(distributed_graph)

            if(not args.no_eager):
                eager_distributed_graph = add_eager_nodes(distributed_graph, args.dgsh_tee)
            else:
                eager_distributed_graph = distributed_graph

            ## Assert that the graph stayed valid after all transformations
            assert(eager_distributed_graph.valid())

            ## Print statistics of output nodes
            print_graph_statistics(eager_distributed_graph)
            # log(eager_distributed_graph)

            optimized_asts_and_irs.append(eager_distributed_graph)
        else:
            optimized_asts_and_irs.append(ast_or_ir)

    optimization_end_time = datetime.now()
    print_time_delta("Optimization", optimization_start_time, optimization_end_time, args)

    return optimized_asts_and_irs


def print_graph_statistics(graph):
    total_nodes = graph.nodes
    cat_nodes = [node for node in total_nodes.values() if isinstance(node, Cat)]
    eager_nodes = [node for node in total_nodes.values() if isinstance(node, Eager)]
    log("Total nodes after optimization:", len(total_nodes))
    log(" -- out of which:")
    log("Cat nodes:", len(cat_nodes))
    log("Eager nodes:", len(eager_nodes))

## This is a simplistic planner, that pushes the available
## parallelization from the inputs in file stateless commands. The
## planner starts from the sources of the graph, and pushes
## file parallelization as far as possible.
##
## It returns a maximally expanded (regarding files) graph, that can
## be scheduled depending on the available computational resources.
def naive_parallelize_stateless_nodes_bfs(graph, fan_out, batch_size, no_cat_split_vanish,
                                          r_split_flag, r_split_batch_size):
    source_node_ids = graph.source_nodes()

    ## Generate a fileIdGen from a graph, that doesn't clash with the
    ## current graph fileIds.
    fileIdGen = graph.get_file_id_gen()

    ## Starting from the sources of the graph traverse the whole graph using a
    ## node_id workset. Every iteration we add the next nodes to the workset as
    ## well as any newly added nodes due to optimizations.
    workset = source_node_ids
    visited = set()
    while (len(workset) > 0):
        curr_id = workset.pop(0)
        assert(isinstance(curr_id, int))
        ## Node must not be in visited, but must also be in the graph
        ## (because it might have been deleted after some
        ## optimization).
        if(not curr_id in visited
           and curr_id in graph.nodes):
            # log("Curr id:", curr_id)
            visited.add(curr_id)
            next_node_ids = graph.get_next_nodes(curr_id)
            workset += next_node_ids

            new_nodes = parallelize_cat(curr_id, graph, fileIdGen,
                                        fan_out, batch_size, no_cat_split_vanish,
                                        r_split_flag, r_split_batch_size)

            ## Assert that the graph stayed valid after the transformation
            ## TODO: Do not run this everytime in the loop if we are not in debug mode.
            # log("Graph nodes:", graph.nodes)
            # log("Graph edges:", graph.edges)
            # assert(graph.valid())

            ## Add new nodes to the workset depending on the optimization.
            ##
            ## WARNING: There is an assumption here that if there are new
            ## nodes there was an optimization that happened and these new
            ## nodes should ALL be added to the workset. Even if that is
            ## correct, that is certainly non-optimal.
            ##
            ## TODO: Fix that
            if(len(new_nodes) > 0):
                # log("New nodes:", new_nodes)
                workset += [node.get_id() for node in new_nodes]

    return graph


## Optimizes several commands by splitting its input
def split_command_input(curr, graph, fileIdGen, fan_out, _batch_size, r_split_flag, r_split_batch_size):
    assert(curr.is_parallelizable())
    assert(not isinstance(curr, Cat))
    assert(fan_out > 1)

    ## At the moment this only works for nodes that have one input.
    ##
    ## TODO: Extend it to work for nodes that have more than one input.
    ##       This has to be done to be able to parallelize comm
    number_of_previous_nodes = len(curr.get_input_list())
    new_merger = None
    if (number_of_previous_nodes == 1):
        ## If the previous command is either a cat with one input, or
        ## if it something else

        input_ids = curr.get_input_list()
        assert(len(input_ids) == 1)
        input_id = input_ids[0]

        ## First we have to make the split file commands.
        split_file_commands, output_fids = make_split_files(input_id, fan_out, fileIdGen, r_split_flag, r_split_batch_size)
        for output_fid in output_fids:
            output_fid.make_ephemeral()
            graph.add_edge(output_fid)

        for split_file_command in split_file_commands:
            graph.add_node(split_file_command)

        ## With the split file commands in place and their output
        ## fids (and this commands new input ids, we have to
        ## create a new Cat node (or modify the existing one) to
        ## have these as inputs, and connect its output to our
        ## input.

        ## Generate a new file id for the input of the current command.
        new_input_fid = fileIdGen.next_file_id()
        new_input_fid.make_ephemeral()
        graph.add_edge(new_input_fid)
        new_input_id = new_input_fid.get_ident()

        output_ids = [fid.get_ident() for fid in output_fids]

        ## If we add r_split, then the merger is actually an r_merge
        if(r_split_flag):
            new_merger = r_merge.make_r_merge_node(output_ids, new_input_id)
        else:
            new_merger = make_cat_node(output_ids, new_input_id)
        graph.add_node(new_merger)

        ## Replace the previous input edge with the new input edge that is after the cat.
        curr.replace_edge(input_id, new_input_id)
        graph.set_edge_to(new_input_id, curr.get_id())

        # log("graph nodes:", graph.nodes)
        # log("graph edges:", graph.edges)

    return new_merger


## TODO: There needs to be some state to keep track of open r-split sessions
##       (that either end at r-merge or at r_unwrap before a commutative command).
##
## TODO: At the moment we greedily try to add r-splits if possible, so we need to have a better procedure of deciding whether to put them or not.
##       For example for non-commutative pure commands.

## If the current command is a cat, and is followed by a node that
## is either stateless or pure parallelizable, commute the cat
## after the node.
def parallelize_cat(curr_id, graph, fileIdGen, fan_out,
                    batch_size, no_cat_split_vanish, r_split_flag, r_split_batch_size):
    curr = graph.get_node(curr_id)
    new_nodes_for_workset = []

    # log("Check to parallelize curr:", curr)

    ## Get next nodes in the graph
    next_node_ids = graph.get_next_nodes(curr_id)

    ## We try to parallelize for all the edges that go out from the current node and into another node
    for next_node_id in next_node_ids:
        next_node = graph.get_node(next_node_id)
        # log("|-- its next node is:", next_node)
        new_curr = curr
        new_curr_id = curr_id

        ## If the next node can be parallelized, then we should try to parallelize
        ##
        ## If the user has provided the r_split flag (they want to use r_split), 
        ## then parallelizability depends on commutativity (if a command is pure parallelizable but not commutative)
        ## then it can't be parallelized. Therefore we do not parallelize non-commutative pure parallelizable commands.
        ##
        ## TODO: We need to extend PaSh to have a mode where it can have both r_splits and auto_split if a command is not
        ##       commutative. This can be added as an option to the r_split flag, e.g., r_split="no" | "yes" | "optimal".
        if(next_node.is_parallelizable()
           and not isinstance(next_node, Cat)
           and (not r_split_flag
                or (next_node.is_commutative()
                    or next_node.is_stateless()))):
            ## If the current node is not a merger, it means that we need
            ## to generate a merger using a splitter (auto_split or r_split)

            ## no_cat_split_vanish shortcircuits this and inserts a split even if the current node is a cat.
            if(fan_out > 1
               and (no_cat_split_vanish
                    or (not (isinstance(curr, Cat)
                             or isinstance(curr, r_merge.RMerge))
                        or ((isinstance(curr, Cat)
                             or isinstance(curr, r_merge.RMerge))
                            and len(curr.get_input_list()) < fan_out)))):
                new_merger = split_command_input(next_node, graph, fileIdGen, fan_out, batch_size, r_split_flag, r_split_batch_size)

                ## After split has succeeded we know that the curr node (previous of the next)
                ## has changed. Therefore we need to retrieve it again.
                if (not new_merger is None):
                    new_curr_id = new_merger.get_id()
                    new_curr = new_merger
                    assert(isinstance(new_curr, Cat)
                           or isinstance(new_curr, r_merge.RMerge))

            ## If curr is cat, it means that split suceeded, or it was
            ## already a cat. In any case, we can proceed with the
            ## parallelization.
            ##
            ## Both Cat and RMerge can be "commuted" with parallelizable nodes
            if(isinstance(new_curr, Cat)
               or isinstance(new_curr, r_merge.RMerge)):
                new_nodes = check_parallelize_dfg_node(new_curr_id, next_node_id, graph, fileIdGen)
                # log("New nodes:", new_nodes)
                new_nodes_for_workset += new_nodes

    return new_nodes_for_workset

## TODO: Instead of moving a cat after a node, we need to parallelize cat,
##       then remove cat (since it takes a single input to a single output),
##       then parallelize the next node. This will allow us to handle `comm -23 p1 p2`
##
## TODO: A nice interface would be (check/apply transformation)
##
## TODO: This could be a method of IR.
##
## TODO: We need to check if the previous node is a cat or a merge
def check_parallelize_dfg_node(merger_id, node_id, graph, fileIdGen):

    ## Get merger inputs (cat or r_merge).
    merger_input_edge_ids = graph.get_node_input_ids(merger_id)

    ## If the merger has more than one input, then the next node could be parallelized
    new_nodes = []
    if (len(merger_input_edge_ids) > 1):
        ## If the merger is r-merge, then the next node needs to either be stateless, or commutative parallelizable.
        merger = graph.get_node(merger_id)
        node = graph.get_node(node_id)
        if((isinstance(merger, Cat)
            and node.is_parallelizable())
           or (isinstance(merger, r_merge.RMerge)
               and (node.is_stateless()
                    or node.is_commutative()))):
            new_nodes = parallelize_dfg_node(merger_id, node_id, graph, fileIdGen)

    return new_nodes

def parallelize_dfg_node(old_merger_id, node_id, graph, fileIdGen):
    node = graph.get_node(node_id)
    assert(node.is_parallelizable())

    ## TODO: Delete this
    ## Get cat inputs and output. Note that there is only one output.
    # old_merger_input_edge_ids = graph.get_node_input_ids(old_merger_id)
    # old_merger_output_edge_ids = graph.get_node_output_ids(old_merger_id)
    # assert(len(old_merger_output_edge_ids) == 1)
    # old_merger_output_edge_id = old_merger_output_edge_ids[0]

    new_nodes = []
    ## We assume that every stateless and pure parallelizable command has one output_file_id for now.
    ##
    ## TODO: Check if this can be lifted.
    node_output_edge_ids = graph.get_node_output_ids(node_id)
    assert(len(node_output_edge_ids) == 1)
    node_output_edge_id = node_output_edge_ids[0]

    ## TODO: Add a commutativity check before actually applying this transformation if the current node is pure parallelizable.
    new_parallel_nodes, map_output_ids = graph.parallelize_node(node_id, fileIdGen)
    new_nodes += new_parallel_nodes

    # log("after duplicate graph nodes:", graph.nodes)
    # log("after duplicate graph edges:", graph.edges)

    ## Make a merge command that joins the results of all the duplicated commands
    ##
    ## TODO: We need to figure out what to do with r_merge when commands are not commutative
    if(node.is_pure_parallelizable()):
        merge_commands, new_edges, final_output_id = create_merge_commands(node,
                                                                           map_output_ids,
                                                                           fileIdGen)
        graph.add_edges(new_edges)

        ## Add the merge commands in the graph
        for merge_command in merge_commands:
            graph.add_node(merge_command)

        ## Replace the previous final_output_id with the previous id
        final_merge_node_id = graph.edges[final_output_id][1]
        final_merge_node = graph.get_node(final_merge_node_id)
        final_merge_node.replace_edge(final_output_id, node_output_edge_id)
        graph.set_edge_from(node_output_edge_id, final_merge_node_id)
        graph.set_edge_from(final_output_id, None)

        ## Only add the final node to the new_nodes
        new_nodes.append(final_merge_node)


    # log("after merge graph nodes:", graph.nodes)
    # log("after merge graph edges:", graph.edges)

    ## WARNING: In order for the above to not mess up
    ## anything, there must be no other node that writes to
    ## the same output as the curr node. Otherwise, the above
    ## procedure will mess this up.
    ##
    ## TODO: Either make an assertion to catch any case that
    ## doesn't satisfy the above assumption here, or extend
    ## the intermediate representation and the above procedure
    ## so that this assumption is lifted (either by not
    ## parallelizing, or by properly handling this case)
    return new_nodes

## Creates a merge command for all pure commands that can be
## parallelized using a map and a reduce/merge step
def create_merge_commands(curr, new_output_ids, fileIdGen):
    if(str(curr.com_name) == "sort"):
        return create_sort_merge_commands(curr, new_output_ids, fileIdGen)
    elif(str(curr.com_name) == "custom_sort"):
        return create_sort_merge_commands(curr, new_output_ids, fileIdGen)
    elif(str(curr.com_name) == "bigrams_aux"):
        return create_bigram_aux_merge_commands(curr, new_output_ids, fileIdGen)
    elif(str(curr.com_name) == "alt_bigrams_aux"):
        return create_alt_bigram_aux_merge_commands(curr, new_output_ids, fileIdGen)
    elif(str(curr.com_name) == "uniq"):
        return create_uniq_merge_commands(curr, new_output_ids, fileIdGen)
    else:
        raise NotImplementedError()

## TODO: These must be generated using some file information
##
## TODO: Find a better place to put these functions
def create_sort_merge_commands(curr, new_output_ids, fileIdGen):
    output = create_reduce_tree(lambda ids: SortGReduce(curr, ids),
                                new_output_ids, fileIdGen)
    return output

def create_bigram_aux_merge_commands(curr, new_output_ids, fileIdGen):
    output = create_reduce_tree(lambda ids: BigramGReduce(curr, ids),
                                new_output_ids, fileIdGen)
    return output

def create_alt_bigram_aux_merge_commands(curr, new_output_ids, fileIdGen):
    output = create_reduce_tree(lambda ids: AltBigramGReduce(curr, ids),
                                new_output_ids, fileIdGen)
    return output

## Instead of creating a tree, we just create a single level reducer for uniq
def create_uniq_merge_commands(curr, new_output_ids, fileIdGen):
    ## Make an intermediate cat node
    intermediate_fid = fileIdGen.next_ephemeral_file_id()
    intermediate_id = intermediate_fid.get_ident()
    new_cat = make_cat_node(flatten_list(new_output_ids), intermediate_id)

    ## Make the new uniq output
    new_out_fid = fileIdGen.next_ephemeral_file_id()
    new_out_id = new_out_fid.get_ident()

    ## TODO: Pass the options of `curr` correctly

    ## Make the uniq merge node
    uniq_com_name = Arg(string_to_argument("uniq"))
    com_category = "pure_parallelizable"
    node = DFGNode([intermediate_id],
                   [new_out_id],
                   uniq_com_name,
                   com_category)

    return ([new_cat, node], [intermediate_fid, new_out_fid], new_out_id)

## This function creates the reduce tree. Both input and output file
## ids must be lists of lists, as the input file ids and the output
## file ids might contain auxiliary files.
def create_reduce_tree(init_func, input_ids, fileIdGen):
    tree = []
    new_edges = []
    curr_ids = input_ids
    while(len(curr_ids) > 1):
        new_level, curr_ids, new_fids = create_reduce_tree_level(init_func, curr_ids, fileIdGen)
        tree += new_level
        new_edges += new_fids

    ## Find the final output
    final_output_id = curr_ids[0][0]

    ## Drain the final auxiliary outputs
    final_auxiliary_outputs = curr_ids[0][1:]
    drain_fids = [fileIdGen.next_file_id()
                  for final_auxiliary_output in final_auxiliary_outputs]
    for drain_fid in drain_fids:
        drain_fid.set_resource(FileResource(Arg(string_to_argument('/dev/null'))))
        new_edges.append(drain_fid)
    drain_ids = [fid.get_ident() for fid in drain_fids]

    drain_cat_commands = [make_cat_node([final_auxiliary_output], drain_id)
                          for final_auxiliary_output, drain_id in zip(final_auxiliary_outputs, drain_ids)]
    return (tree + drain_cat_commands), new_edges, final_output_id


## This function creates a level of the reduce tree. Both input and
## output file ids must be lists of lists, as the input file ids and
## the output file ids might contain auxiliary files.
def create_reduce_tree_level(init_func, input_ids, fileIdGen):
    if(len(input_ids) % 2 == 0):
        output_ids = []
        even_input_ids = input_ids
    else:
        output_ids = [input_ids[0]]
        even_input_ids = input_ids[1:]

    new_fids = []
    level = []
    for i in range(0, len(even_input_ids), 2):
        new_out_fids = [fileIdGen.next_ephemeral_file_id() for _ in input_ids[i]]
        new_fids += new_out_fids
        new_out_ids = [fid.get_ident() for fid in new_out_fids]
        output_ids.append(new_out_ids)
        new_node = create_reduce_node(init_func, even_input_ids[i:i+2], new_out_ids)
        level.append(new_node)
    return (level, output_ids, new_fids)

## This function creates one node of the reduce tree
def create_reduce_node(init_func, input_ids, output_ids):
    return init_func(flatten_list(input_ids) + output_ids)


## This functions adds an eager on a given edge.
def add_eager(eager_input_id, graph, fileIdGen, intermediateFileIdGen, use_dgsh_tee):
    new_fid = fileIdGen.next_ephemeral_file_id()
    new_id = new_fid.get_ident()

    if use_dgsh_tee:
        ## TODO: seperate to better use dgsh-tee params and maybe deprecate eager
        eager_node = dgsh_tee.make_dgsh_tee_node(eager_input_id, new_id)
    else:
        ## TODO: Remove the line below if eager creates its intermediate file
        ##       on its own.
        intermediate_fid = intermediateFileIdGen.next_ephemeral_file_id()

        eager_exec_path = '{}/{}'.format(config.PASH_TOP, runtime_config['eager_executable_path'])

        eager_node = make_eager_node(eager_input_id, new_id, intermediate_fid, eager_exec_path)

    ## Add the edges and the nodes to the graph
    graph.add_edge(new_fid)

    ## Modify the next node inputs to be the new inputs
    next_node_id = graph.edges[eager_input_id][2]
    if(not next_node_id is None):
        next_node = graph.get_node(next_node_id)
        next_node.replace_edge(eager_input_id, new_id)
        graph.set_edge_to(new_id, next_node_id)

    graph.add_node(eager_node)


## This function adds eager nodes wherever the width of graph is
## becoming smaller.
def add_eager_nodes(graph, use_dgsh_tee):
    source_node_ids = graph.source_nodes()

    ## Generate a fileIdGen that doesnt clash with graph fids.
    fileIdGen = graph.get_file_id_gen()
    intermediateFileIdGen = FileIdGen(0, runtime_config['eager_intermediate_prefix'])

    ## Get the next nodes
    workset = [node for source_node_id in source_node_ids for node in graph.get_next_nodes(source_node_id)]
    visited = set()
    while (len(workset) > 0):
        curr_id = workset.pop(0)
        curr = graph.get_node(curr_id)
        if (not curr_id in visited):
            visited.add(curr_id)
            next_node_ids = graph.get_next_nodes(curr_id)
            workset += next_node_ids

            ## TODO: Make sure that we don't add duplicate eager nodes

            ## Add eager nodes if the node has more than one input
            curr_input_ids = graph.get_node_input_ids(curr_id)
            if (len(curr_input_ids) > 1):
                ## TODO: If we know that a command reads its inputs in a list,
                ##       then we might not need to put an eager on its first input.
                ## Note: This cannot be done for `sort -m` so we need to know in the
                ##       annotations whether input consumption is in order or not.

                for curr_input_id in curr_input_ids:
                    _fid, from_node, to_node = graph.edges[curr_input_id]
                    assert(to_node == curr_id)
                    ## If the edge is an input edge, then we don't want to put eager.
                    if(not from_node is None):
                        add_eager(curr_input_id, graph, fileIdGen, intermediateFileIdGen, use_dgsh_tee)

            if(isinstance(curr, Split)):
                eager_input_ids = curr.outputs[:-1]
                for edge_id in eager_input_ids:
                    add_eager(edge_id, graph, fileIdGen, intermediateFileIdGen, use_dgsh_tee)

            ## Add an eager after r_unwrap            
            if(isinstance(curr, r_unwrap.RUnwrap)):
                eager_input_id = curr.outputs[0]
                add_eager(eager_input_id, graph, fileIdGen, intermediateFileIdGen, use_dgsh_tee)

            ## Add an eager after r_split
            if(isinstance(curr, r_split.RSplit)):
                eager_input_ids = curr.outputs
                for edge_id in eager_input_ids:
                    add_eager(edge_id, graph, fileIdGen, intermediateFileIdGen, use_dgsh_tee)

    return graph






    ## TODO: In order to be able to execute it, we either have to
    ## execute it in the starting shell (so that we have its state),
    ## or we should somehow pass the parent shell's state to the the
    ## distribution planner, and then the implementation environment.
    ## In general, we probably have to find a way to pass around a
    ## shell's state, as this will be essential for the distributed
    ## setting too.
    ##
    ## Note: A way to do this is by using set > temp_file. Source:
    ## https://arstechnica.com/civis/viewtopic.php?f=16&t=805521

    ## TODO: We have to handle xargs in a special way. First of all,
    ## in order to parallelize the command that xarg runs, we have to
    ## do xargs -L 1 (or some other number) so that for every -L
    ## lines, it calls a different instance of the command. Then it
    ## will be parallelizable. In addition, we have to somehow
    ## statically decide how much we will parallelize xarg, and how
    ## many lines are going to be sent to each operator.
    ##
    ## This can probably be solved if we allow partial files in files
    ## without resources.

    ## TODO: There is slight problem with *, and other expansions in
    ## the shell. The normal shell semantics is to expand the strings
    ## in a command that is in a pipeline after the different
    ## subshells have been spawned. However, we would like to have all
    ## strings expanded as much as possible, so that we can statically
    ## make choices about how much to distribute each command.
    ##
    ## Maybe we should run expansions on our own, before calling the
    ## distribution planner? Or in the distribution planner itself? It
    ## seems that the distribution planner should be able to do some
    ## expansion itself though

    ## TODO: There is a problem when given an unexpanded string. It
    ## might be many files, so spliting the file up in different
    ## pieces might be wrong.

    ## BIG TODO: Extend the file class so that it supports tee etc.

if __name__ == "__main__":
    main()
