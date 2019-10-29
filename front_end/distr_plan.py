import sys
import pickle
from ir import *
from json_ast import *

## This file receives the name of a file that holds an IR, reads the
## IR, read some configuration file with node information, and then
## should make a distribution plan for it.

def main():
    # print command line arguments
    ir_filename = sys.argv[1]
    with open(ir_filename, "rb") as ir_file:
        ir_node = pickle.load(ir_file)

    print("Retrieving IR: {} ...".format(ir_filename))
    shell_string = ast_to_shell(ir_node.ast)
    print(shell_string)

    simpl_file_distribution_planner(ir_node)

    
    ## Notes:
    ##
    ## Each node in the graph has one input stream and one output
    ## stream.
    ##
    ## However, the input (and the output) might be in several
    ## different "locations". So the input (and output) can be
    ## represented as a sequence of resources. These can be files,
    ## urls, blocks of files in HDFS, etc.
    ##
    ## The distribution planner takes a graph, where the edges
    ## arriving to a node are uniquely numbered depending on the
    ## position that they have in the sequence of inputs to the
    ## incoming node.
    ##
    ## The distribution planner also takes information about the
    ## available computational resources, such as nodes in the system,
    ## and their cores, etc.

## This is a simplistic planner, that pushes the available
## parallelization from the inputs in file stateless commands. The
## planner starts from the sources of the graph, and pushes
## file parallelization as far as possible.
##
## It returns a maximally expanded (regarding files) graph, that can
## be scheduled depending on the available computational resources.
def simpl_file_distribution_planner(graph):
    print("Intermediate representation:")
    print(graph)

    ## We assume that the file identifiers that have been added in the
    ## intermediate representation show the edges between different IR
    ## nodes.
    ##
    ## We assume that all nodes have an in_stream and an out_stream
    ## list, and that these are the ones which will be used to create
    ## the graph.
    
    ## TODO: Starting from the sources of the graph, if they are
    ## stateless, duplicate the command as many times as the number of
    ## identifiers in its in_stream. Then connect their outputs in
    ## order to next command.
    ##
    ## Note: The above has to be done in a BFS fashion (starting from
    ## all sources simultaneously) so that we don't have to iterate to
    ## reach a fixpoint.
    naive_parallelize_stateless_nodes_bfs(graph)
    print("Parallelized graph:")
    print(graph)

    ## The result of the above steps should be an expanded
    ## intermediate representation graph, that can be then mapped to
    ## real nodes.

def naive_parallelize_stateless_nodes_bfs(graph):
    source_nodes = graph.source_nodes()
    print("Source nodes:")
    print(source_nodes)

    nodes = source_nodes
    while (len(nodes) > 0):
        curr = nodes.pop(0)

        next_nodes = graph.get_next_nodes(curr)
        nodes += next_nodes
        ## If the command is stateless and has more than one inputs,
        ## it can be parallelized
        if (curr.category == "stateless" and len(curr.in_stream) > 0):
            print("To parallelize:")
            print(curr)
            print("Next nodes:")
            print(next_nodes)
            ## TODO: Parallelize the stateless by finding the location
            ## of its outgoing fid in each next node. Then, in its
            ## place, generate as many files as the size of the
            ## in_stream. Duplicate the current node as many times as
            ## the input stream and give its output file identifiers
            ## the generated fids in order.
            ##
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

            ## TODO: In order to do this, I have to generate a
            ## fileIdGen from a graph, that doesn't class with the
            ## current graph fileIds.




    
    ## TODO: As an integration experiment make a distribution planner
    ## that just uses Greenberg's parser to output shell code from the
    ## original AST of the IR, and just execute that.

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


    ## Old Notes:
    ##
    ## A distribution planner that uses equations (like the ones we
    ## have described with ++) could be separated into three parts:
    ##
    ## 1. Use the equations exhaustively (or until some bound) to
    ##    expose any possible parallelism and distribution. This
    ##    requires that applying equations has a normal form, either
    ##    because they can only be applied a finite number of times,
    ##    or because we have a normal form for equations that can be
    ##    applied an infinite amount of times, that is succinct.
    ##
    ## 2. Assign each node of the IR to a physical node in the system.
    ##
    ## 3. Reapply the equalities (the other way around) so that
    ##    operations on the same node can be merged together to
    ##    improve performance.
        
if __name__ == "__main__":
    main()
    
