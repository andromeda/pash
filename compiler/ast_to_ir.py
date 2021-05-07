from ast_util import *
from ir import *
from definitions.ast_node import *
from definitions.ast_node_c import *
from util import *
from json_ast import save_asts_json, ast_to_shell
from parse import parse_shell, from_ast_objects_to_shell, from_ast_objects_to_shell_file
from expand import *
import subprocess
import traceback

import config

import pickle


##
## Compile AST -> Extended AST with IRs
##

## Compiles a given AST to an intermediate representation tree, which
## has some subtrees in it that are graphs representing a distributed
## computation.
##
## The above assumes that subtrees of the AST are disjoint
## computations that can be distributed separately (locally/modularly)
## without knowing about previous or later subtrees that can be
## distributed. Is that reasonable?
compile_cases = {
        "Pipe": (lambda fileIdGen, config:
                 lambda ast_node: compile_node_pipe(ast_node, fileIdGen, config)),
        "Command": (lambda fileIdGen, config:
                    lambda ast_node: compile_node_command(ast_node, fileIdGen, config)),
        "And": (lambda fileIdGen, config:
                lambda ast_node: compile_node_and_or_semi(ast_node, fileIdGen, config)),
        "Or": (lambda fileIdGen, config:
               lambda ast_node: compile_node_and_or_semi(ast_node, fileIdGen, config)),
        "Semi": (lambda fileIdGen, config:
                 lambda ast_node: compile_node_and_or_semi(ast_node, fileIdGen, config)),
        "Redir": (lambda fileIdGen, config:
                  lambda ast_node: compile_node_redir_subshell(ast_node, fileIdGen, config)),
        "Subshell": (lambda fileIdGen, config:
                     lambda ast_node: compile_node_redir_subshell(ast_node, fileIdGen, config)),
        "Background": (lambda fileIdGen, config:
                       lambda ast_node: compile_node_background(ast_node, fileIdGen, config)),
        "Defun": (lambda fileIdGen, config:
                  lambda ast_node: compile_node_defun(ast_node, fileIdGen, config)),
        "For": (lambda fileIdGen, config:
                  lambda ast_node: compile_node_for(ast_node, fileIdGen, config))
        }

preprocess_cases = {
    "Pipe": (lambda irFileGen, config:
             lambda ast_node: preprocess_node_pipe(ast_node, irFileGen, config)),
    "Command": (lambda irFileGen, config:
                lambda ast_node: preprocess_node_command(ast_node, irFileGen, config)),
    "Background": (lambda irFileGen, config:
                   lambda ast_node: preprocess_node_background(ast_node, irFileGen, config)),
    "Subshell": (lambda irFileGen, config:
                   lambda ast_node: preprocess_node_subshell(ast_node, irFileGen, config)),
    "For": (lambda irFileGen, config:
            lambda ast_node: preprocess_node_for(ast_node, irFileGen, config)),
    "While": (lambda irFileGen, config:
              lambda ast_node: preprocess_node_while(ast_node, irFileGen, config)),
    "Defun": (lambda irFileGen, config:
              lambda ast_node: preprocess_node_defun(ast_node, irFileGen, config)),
    "Semi": (lambda irFileGen, config:
             lambda ast_node: preprocess_node_semi(ast_node, irFileGen, config)),
    "Or": (lambda irFileGen, config:
           lambda ast_node: preprocess_node_or(ast_node, irFileGen, config)),
    "And": (lambda irFileGen, config:
            lambda ast_node: preprocess_node_and(ast_node, irFileGen, config)),
    "Not": (lambda irFileGen, config:
            lambda ast_node: preprocess_node_not(ast_node, irFileGen, config)),
    "If": (lambda irFileGen, config:
            lambda ast_node: preprocess_node_if(ast_node, irFileGen, config)),
    "Case": (lambda irFileGen, config:
             lambda ast_node: preprocess_node_case(ast_node, irFileGen, config))
}

ir_cases = {
        ## Note: We should never encounter a Pipe construct, since all
        ## of them must have been become IRs
        ##
        ## "Pipe": (lambda c, b, i: {c : [b, i]}),
        "Command":   (lambda irFileGen, config:
                      lambda ast_node: replace_irs_command(ast_node, irFileGen, config)),
        "And" :      (lambda irFileGen, config:
                      lambda ast_node: replace_irs_and_or_semi(ast_node, irFileGen, config)),
        "Or" :       (lambda irFileGen, config:
                      lambda ast_node: replace_irs_and_or_semi(ast_node, irFileGen, config)),
        "Semi" :     (lambda irFileGen, config:
                      lambda ast_node: replace_irs_and_or_semi(ast_node, irFileGen, config)),

        ## TODO: Complete these
        # "Redir" : (lambda c, l, n, r: compile_node_redir(c, l, n, r, fileIdGen)),
        # "Subshell" : (lambda c, l, n, r: compile_node_subshell(c, l, n, r, fileIdGen)),
        # "Background" : (lambda c, l, n, r: compile_node_background(c, l, n, r, fileIdGen)),
        # "Defun" : (lambda c, l, n, b: compile_node_defun(c, l, n, b, fileIdGen)),
        "For" :      (lambda irFileGen, config:
                      lambda ast_node: replace_irs_for(ast_node, irFileGen, config)),
        }

def compile_asts(ast_objects, fileIdGen, config):
    compiled_asts = []
    acc_ir = None
    for i, ast_object in enumerate(ast_objects):
        # log("Compiling AST {}".format(i))
        # log(ast_object)

        ## Compile subtrees of the AST to out intermediate representation
        expanded_ast = expand_command(ast_object, config)
        compiled_ast = compile_node(expanded_ast, fileIdGen, config)

        # log("Compiled AST:")
        # log(compiled_ast)

        ## If the accumulator contains an IR (meaning that the
        ## previous commands where run in background), union it with
        ## the current returned ast.
        if (not acc_ir is None):

            if (isinstance(compiled_ast, IR)):
                acc_ir.background_union(compiled_ast)
            else:
                ## TODO: Make this union the compiled_ast with the
                ## accumulated IR, since the user wanted to run these
                ## commands in parallel (Is that correct?)
                # acc_ir.background_union(IR([compiled_ast]))
                compiled_asts.append(acc_ir)
                acc_it = None
                compiled_asts.append(compiled_ast)

            ## If the current compiled ast not in background (and so
            ## the union isn't in background too), stop accumulating
            if (not acc_ir is None
                and not acc_ir.is_in_background()):
                compiled_asts.append(acc_ir)
                acc_ir = None
        else:
            ## If the compiled ast is in background, start
            ## accumulating it
            if (isinstance(compiled_ast, IR)
                and compiled_ast.is_in_background()):
                acc_ir = compiled_ast
            else:
                compiled_asts.append(compiled_ast)

    ## The final accumulator
    if (not acc_ir is None):
        compiled_asts.append(acc_ir)

    return compiled_asts


def compile_node(ast_object, fileIdGen, config):
    global compile_cases
    return ast_match(ast_object, compile_cases, fileIdGen, config)

def compile_node_pipe(ast_node, fileIdGen, config):
    compiled_pipe_nodes = combine_pipe([compile_node(pipe_item, fileIdGen, config)
                                        for pipe_item in ast_node.items])

    ## Note: When calling combine_pipe_nodes (which
    ##       optimistically distributes all the children of a
    ##       pipeline) the compiled_pipe_nodes should always
    ##       be one IR
    compiled_ir = compiled_pipe_nodes[0]
    ## Note: Save the old ast for the end-to-end prototype
    old_ast_node = make_kv(ast_node.construct.value, [ast_node.is_background, ast_node.items])
    compiled_ir.set_ast(old_ast_node)
    ## Set the IR background so that it can be parallelized with
    ## the next command if the pipeline was run in background
    compiled_ir.set_background(ast_node.is_background)
    ## TODO: If the pipeline is in background, I also have to
    ## redirect its stdin, stdout
    compiled_ast = compiled_ir
    return compiled_ast

## This combines all the children of the Pipeline to an IR.
def combine_pipe(ast_nodes):
    ## Initialize the IR with the first node in the Pipe
    if (isinstance(ast_nodes[0], IR)):
        combined_nodes = ast_nodes[0]
    else:
        ## If any part of the pipe is not an IR, the compilation must fail.
        log("Node: {} is not pure".format(ast_nodes[0]))
        exit(1)

    ## Combine the rest of the nodes
    for ast_node in ast_nodes[1:]:
        if (isinstance(ast_node, IR)):
            combined_nodes.pipe_append(ast_node)
        else:
            ## If any part of the pipe is not an IR, the compilation must fail.
            log("Node: {} is not pure".format(ast_nodes))
            exit(1)

    return [combined_nodes]

def compile_node_command(ast_node, fileIdGen, config):
    construct_str = ast_node.construct.value
    old_ast_node = make_kv(construct_str, [ast_node.line_number,
        ast_node.assignments, ast_node.arguments, ast_node.redir_list])

    ## TODO: Do we need the line number?

    ## Compile assignments and redirection list
    compiled_assignments = compile_assignments(ast_node.assignments, fileIdGen, config)
    compiled_redirections = compile_redirections(ast_node.redir_list, fileIdGen, config)

    ## If there are no arguments, the command is just an
    ## assignment
    if(len(ast_node.arguments) == 0):
        ## Just compile the assignments. Specifically compile the
        ## assigned values, because they might have command
        ## substitutions etc..
        compiled_ast = make_kv(construct_str, [ast_node.line_number] +
                               [compiled_assignments] + [ast_node.arguments, compiled_redirections])
    else:
        arguments = ast_node.arguments
        command_name = arguments[0]
        options = compile_command_arguments(arguments[1:], fileIdGen, config)

        ## Question: Should we return the command in an IR if one of
        ## its arguments is a command substitution? Meaning that we
        ## will have to wait for its command to execute first?
        ##
        ## ANSWER: Kind of. If a command has a command substitution or
        ## anything that evaluates we should add it to the IR, but we
        ## should also make sure that its category is set to the most
        ## general one. That means that it can be executed
        ## concurrently with other commands, but it cannot be
        ## parallelized.
        try:
            ## If the command is not compileable to a DFG the following call will fail
            ir = compile_command_to_DFG(fileIdGen,
                                        command_name,
                                        options,
                                        redirections=compiled_redirections)
            compiled_ast = ir
        except ValueError as err:
            ## TODO: Delete this log from here
            log(err)
            ## TODO: Maybe we want to fail here instead of waiting for later?
            ##       Is there any case where a non-compiled command is fine?
            # log(traceback.format_exc())
            compiled_arguments = compile_command_arguments(arguments, fileIdGen, config)
            compiled_ast = make_kv(construct_str,
                                   [ast_node.line_number, compiled_assignments,
                                    compiled_arguments, compiled_redirections])

        return compiled_ast

def compile_node_and_or_semi(ast_node, fileIdGen, config):
    compiled_ast = make_kv(ast_node.construct.value,
            [compile_node(ast_node.left_operand, fileIdGen, config),
             compile_node(ast_node.right_operand, fileIdGen, config)])
    return compiled_ast

def compile_node_redir_subshell(ast_node, fileIdGen, config):
    compiled_node = compile_node(ast_node.node, fileIdGen, config)

    if (isinstance(compiled_node, IR)):
        ## TODO: I should use the redir list to redirect the files of
        ##       the IR accordingly
        compiled_ast = compiled_node
    else:
        compiled_ast = make_kv(ast_node.construct.value, [ast_node.line_number,
            compiled_node, ast_node.redir_list])

    return compiled_ast

def compile_node_background(ast_node, fileIdGen, config):
    compiled_node = compile_node(ast_node.node, fileIdGen, config)

    ## TODO: I should use the redir list to redirect the files of
    ##       the IR accordingly
    if (isinstance(compiled_node, IR)):
        ## TODO: Redirect the stdout, stdin accordingly
        compiled_node.set_background(True)
        compiled_ast = compiled_node
    else:
        ## Note: It seems that background nodes can be added in
        ##       the distributed graph similarly to the children
        ##       of pipelines.
        ##
        ## Question: What happens with the stdin, stdout. Should
        ## they be closed?
        ## TODO: We should not compile the ast here
        compiled_ast = ast_node
        compiled_ast.node = compiled_node

    return compiled_ast

def compile_node_defun(ast_node, fileIdGen, config):
    ## It is not clear how we should handle functions.
    ##
    ## - Should we transform their body to IR?
    ## - Should we handle calls to the functions as commands?
    ##
    ## It seems that we should do both. But we have to think if
    ## this introduces any possible problem.

    ## TODO: Investigate whether it is fine to just compile the
    ##       body of functions.
    compiled_body = compile_node(ast_node.body, fileIdGen, config)
    return make_kv(construct, [ast_node.line_number, ast_node.name, compiled_body])

def compile_node_for(ast_node, fileIdGen, config):
    ## TODO: Investigate what kind of check could we do to make a for
    ## loop parallel
    compiled_ast = make_kv(ast_node.construct.value,
                           [ast_node.line_number,
                            compile_command_argument(ast_node.argument, fileIdGen, config),
                            compile_node(ast_node.body, fileIdGen, config),
                            ast_node.variable])
    return compiled_ast


## This function checks if we should expand an arg_char
##
## It has a dual purpose:
## 1. First, it checks whether we need
##    to pay the overhead of expanding (by checking that there is something to expand)
##    like a variable
## 2. Second it raises an error if we cannot expand an argument.
def should_expand_arg_char(arg_char):
    key, val = get_kv(arg_char)
    if (key in ['V']): # Variable
        return True
    elif (key == 'Q'):
        return should_expand_argument(val)
    elif (key == 'B'):
        log("Cannot expand:", arg_char)
        raise NotImplementedError()
    return False

def should_expand_argument(argument):
    return any([should_expand_arg_char(arg_char) for arg_char in argument])

def make_echo_ast(argument, var_file_path):
    nodes = []
    ## Source variables if present
    if(not var_file_path is None):
        arguments = [string_to_argument("source"), string_to_argument(var_file_path)]

        line_number = 0
        node = make_kv('Command', [line_number, [], arguments, []])
        nodes.append(node)

    ## Reset the exit status
    variable_arg = make_kv('V', ['Normal', "false", 'pash_previous_exit_status', []])
    arguments = [string_to_argument("exit"), [variable_arg]]
    exit_node = make_kv('Command', [0, [], arguments, []])
    node = make_kv('Subshell', [0, exit_node, []])
    nodes.append(node)

    ## Reset the input arguments
    variable_arg = make_kv('V', ['Normal', "false", 'pash_input_args', []])
    arguments = [string_to_argument("set"), string_to_argument("--"), [variable_arg]]
    set_node = make_kv('Command', [0, [], arguments, []])
    nodes.append(set_node)

    arguments = [string_to_argument("echo"), string_to_argument("-n"), argument]

    line_number = 0
    node = make_kv('Command', [line_number, [], arguments, []])
    nodes.append(node)
    return nodes

## TODO: Move this function somewhere more general
def execute_shell_asts(asts):
    output_script = from_ast_objects_to_shell(asts)
    # log(output_script)
    exec_obj = subprocess.run(["/usr/bin/env", "bash"], input=output_script,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
    exec_obj.check_returncode()
    # log(exec_obj.stdout)
    return exec_obj.stdout

## TODO: Properly parse the output of the shell script
def parse_string_to_arguments(arg_char_string):
    # log(arg_char_string)
    return string_to_arguments(arg_char_string)

## TODO: Use "pash_input_args" when expanding in place of normal arguments.
def naive_expand(argument, config):

    ## config contains a dictionary with:
    ##  - all variables, their types, and values in 'shell_variables'
    ##  - the name of a file that contains them in 'shell_variables_file_path'
    # log(config['shell_variables'])
    # log(config['shell_variables_file_path'])

    ## Create an AST node that "echo"s the argument
    echo_asts = make_echo_ast(argument, config['shell_variables_file_path'])

    ## Execute the echo AST by unparsing it to shell
    ## and calling bash
    expanded_string = execute_shell_asts(echo_asts)

    log("Argument:", argument, "was expanded to:", expanded_string)

    ## Parse the expanded string back to an arg_char
    expanded_arguments = parse_string_to_arguments(expanded_string)

    ## TODO: Handle any errors
    # log(expanded_arg_char)
    return expanded_arguments



## This function expands an arg_char.
## At the moment it is pretty inefficient as it serves as a prototype.
##
## TODO: At the moment this has the issue that a command that has the words which we want to expand
##       might have assignments of its own, therefore requiring that we use them to properly expand.
def expand_command_argument(argument, config):
    new_arguments = [argument]
    if(should_expand_argument(argument)):
        new_arguments = naive_expand(argument, config)
    return new_arguments

## This function compiles an arg char by recursing if it contains quotes or command substitution.
##
## It is currently being extended to also expand any arguments that are safe to expand.
def compile_arg_char(arg_char, fileIdGen, config):
    ## Compile the arg char
    key, val = get_kv(arg_char)
    if (key in ['C',   # Single character
                'E']): # Escape
        return arg_char
    elif (key == 'B'):
        ## TODO: I probably have to redirect the input of the compiled
        ##       node (IR) to be closed, and the output to be
        ##       redirected to some file that we will use to write to
        ##       the command argument to complete the command
        ##       substitution.
        compiled_node = compile_node(val, fileIdGen, config)
        return [key, compiled_node]
    elif (key == 'Q'):
        compiled_val = compile_command_argument(val, fileIdGen, config)
        return [key, compiled_val]
    else:
        log("Unknown arg_char:", arg_char)
        ## TODO: Complete this
        return arg_char

def compile_command_argument(argument, fileIdGen, config):
    compiled_argument = [compile_arg_char(char, fileIdGen, config) for char in argument]
    return compiled_argument

def compile_command_arguments(arguments, fileIdGen, config):
    compiled_arguments = [compile_command_argument(arg, fileIdGen, config) for arg in arguments]
    return compiled_arguments

## Compiles the value assigned to a variable using the command argument rules.
## TODO: Is that the correct way to handle them?
def compile_assignments(assignments, fileIdGen, config):
    compiled_assignments = [[assignment[0], compile_command_argument(assignment[1], fileIdGen, config)]
                            for assignment in assignments]
    return compiled_assignments

def compile_redirection(redirection, fileIdGen, config):
    redir_type = redirection[0]
    redir_subtype = redirection[1][0]
    stream_id = redirection[1][1]
    file_arg = compile_command_argument(redirection[1][2], fileIdGen, config)
    return [redir_type, [redir_subtype, stream_id, file_arg]]

def compile_redirections(redirections, fileIdGen, config):
    compiled_redirections = [compile_redirection(redirection, fileIdGen, config)
                             for redirection in redirections]
    return compiled_redirections

##
## Preprocessing
##

## The preprocessing pass replaces all _candidate_ dataflow regions with
## calls to PaSh's runtime to let it establish if they are actually dataflow
## regions. The pass serializes all candidate dataflow regions:
## - A list of ASTs if at the top level or
## - an AST subtree if at a lower level
##
## The PaSh runtime then deserializes them, compiles them (if safe) and optimizes them.

## Replace candidate dataflow AST regions with calls to PaSh's runtime.
def replace_ast_regions(ast_objects, irFileGen, config):
    preprocessed_asts = []
    candidate_dataflow_region = []
    for i, ast_object in enumerate(ast_objects):
        # log("Preprocessing AST {}".format(i))
        # log(ast_object)
        ast, original_text, _linno_before, _linno_after = ast_object
        ## TODO: Turn the untyped ast to an AstNode

        ## Goals: This transformation can approximate in several directions.
        ##        1. Not replacing a candidate dataflow region.
        ##        2. Replacing a too large candidate region
        ##           (making expansion not happen as late as possible)
        ##        3. Not replacing a maximal dataflow region,
        ##           e.g. splitting a big one into two.
        ##        4. Replacing sections that are *certainly* not dataflow regions.
        ##           (This can only lead to performance issues.)
        ##
        ##        Which of the above can we hope to be precise with?
        ##        Can we have proofs indicating that we are not approximating those?

        ## Preprocess ast by replacing subtrees with calls to runtime.
        ## - If the whole AST needs to be replaced (e.g. if it is a pipeline)
        ##   then the second output is true.
        ## - If the next AST needs to be replaced too (e.g. if the current one is a background)
        ##   then the third output is true
        preprocessed_ast_object = preprocess_node(ast, irFileGen, config)
        ## If the dataflow region is not maximal then it implies that the whole
        ## AST should be replaced.
        assert(not preprocessed_ast_object.is_non_maximal() 
               or preprocessed_ast_object.should_replace_whole_ast())
        
        ## If the whole AST needs to be replaced then it implies that
        ## something will be replaced
        assert(not preprocessed_ast_object.should_replace_whole_ast() 
               or preprocessed_ast_object.will_anything_be_replaced())

        ## If it isn't maximal then we just add it to the candidate
        if(preprocessed_ast_object.is_non_maximal()):
            candidate_dataflow_region.append((preprocessed_ast_object.ast,
                                              original_text))
        else:
            ## If the current candidate dataflow region is non-empty
            ## it means that the previous AST was in the background so
            ## the current one has to be included in the process no matter what
            if (len(candidate_dataflow_region) > 0):
                candidate_dataflow_region.append((preprocessed_ast_object.ast,
                                                  original_text))
                ## Since the current one is maximal (or not wholy replaced)
                ## we close the candidate.
                dataflow_region_asts, dataflow_region_lines = unzip(candidate_dataflow_region)
                dataflow_region_text = "\n".join(dataflow_region_lines)
                replaced_ast = replace_df_region(dataflow_region_asts, irFileGen, config,
                                                 ast_text=dataflow_region_text)
                candidate_dataflow_region = []
                preprocessed_asts.append(replaced_ast)
            else:
                if(preprocessed_ast_object.should_replace_whole_ast()):
                    replaced_ast = replace_df_region([preprocessed_ast_object.ast], irFileGen, config,
                                                     ast_text=original_text)
                    preprocessed_asts.append(replaced_ast)
                else:
                    ## In this case, it is possible that no replacement happened,
                    ## meaning that we can simply return the original parsed text as it was.
                    if(preprocessed_ast_object.will_anything_be_replaced()):
                        preprocessed_asts.append(preprocessed_ast_object.ast)
                    else:
                        preprocessed_asts.append(UnparsedScript(original_text))

    ## Close the final dataflow region
    if(len(candidate_dataflow_region) > 0):
        dataflow_region_asts, dataflow_region_lines = unzip(candidate_dataflow_region)
        dataflow_region_text = "\n".join(dataflow_region_lines)
        replaced_ast = replace_df_region(dataflow_region_asts, irFileGen, config,
                                         ast_text=dataflow_region_text)
        candidate_dataflow_region = []
        preprocessed_asts.append(replaced_ast)

    return preprocessed_asts

def preprocess_node(ast_object, irFileGen, config):
    global preprocess_cases
    return ast_match_untyped(ast_object, preprocess_cases, irFileGen, config)

## This preprocesses the AST node and also replaces it if it needs replacement .
## It is called by constructs that cannot be included in a dataflow region.
def preprocess_close_node(ast_object, irFileGen, config):
    preprocessed_ast_object = preprocess_node(ast_object, irFileGen, config)
    preprocessed_ast = preprocessed_ast_object.ast
    should_replace_whole_ast = preprocessed_ast_object.should_replace_whole_ast()
    if(should_replace_whole_ast):
        final_ast = replace_df_region([preprocessed_ast], irFileGen, config)
        something_replaced = True
    else:
        final_ast = preprocessed_ast
        something_replaced = preprocessed_ast_object.will_anything_be_replaced()
    return final_ast, something_replaced

def preprocess_node_pipe(ast_node, _irFileGen, _config):
    ## A pipeline is *always* a candidate dataflow region.
    ## Q: Is that true?

    ## TODO: Preprocess the internals of the pipe to allow
    ##       for mutually recursive calls to PaSh.
    ##
    ##       For example, if a command in the pipe has a command substitution
    ##       in one of its arguments then we would like to call our runtime
    ##       there instead of
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=True,
                                              non_maximal=ast_node.is_background)
    return preprocessed_ast_object

## TODO: Complete this
def preprocess_node_command(ast_node, _irFileGen, _config):
    ## TODO: Preprocess the internals of the pipe to allow
    ##       for mutually recursive calls to PaSh.
    ##
    ##       For example, if a command in the pipe has a command substitution
    ##       in one of its arguments then we would like to call our runtime
    ##       there instead of

    ## If there are no arguments, the command is just an
    ## assignment (Q: or just redirections?)
    if(len(ast_node.arguments) == 0):
        preprocessed_ast_object = PreprocessedAST(ast_node,
                                                  replace_whole=False,
                                                  non_maximal=False,
                                                  something_replaced=False)
        return preprocessed_ast_object

    ## This means we have a command. Commands are always candidate dataflow
    ## regions.
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=True,
                                              non_maximal=False)
    return preprocessed_ast_object

## TODO: Is that correct? Also, this should probably affect `semi`, `and`, and `or`
def preprocess_node_background(ast_node, _irFileGen, _config):
    ## A background node is *always* a candidate dataflow region.
    ## Q: Is that true?

    ## TODO: Preprocess the internals of the background to allow
    ##       for mutually recursive calls to PaSh.
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=True,
                                              non_maximal=True)
    return preprocessed_ast_object

## TODO: We can actually preprocess the underlying node and then
##       return its characteristics above. However, we would need
##       to add a field in the IR that a node runs in a subshell
##       (which would have implications on how the backend outputs it).
##
##       e.g. a subshell node should also be output as a subshell in the backend.
## FIXME: This might not just be suboptimal, but also wrong.
def preprocess_node_subshell(ast_node, irFileGen, config):
    preprocessed_body, something_replaced = preprocess_close_node(ast_node.body,
                                                                  irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.body = preprocessed_body
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=something_replaced)
    return preprocessed_ast_object

## TODO: For all of the constructs below, think whether we are being too conservative

## TODO: This is not efficient at all since it calls the PaSh runtime everytime the loop is entered.
##       We have to find a way to improve that.
def preprocess_node_for(ast_node, irFileGen, config):
    preprocessed_body, something_replaced = preprocess_close_node(ast_node.body, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.body = preprocessed_body
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=something_replaced)
    return preprocessed_ast_object

def preprocess_node_while(ast_node, irFileGen, config):
    preprocessed_test, sth_replaced_test = preprocess_close_node(ast_node.test, irFileGen, config)
    preprocessed_body, sth_replaced_body = preprocess_close_node(ast_node.body, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.test = preprocessed_test
    ast_node.body = preprocessed_body
    something_replaced = sth_replaced_test or sth_replaced_body
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=something_replaced)
    return preprocessed_ast_object

## This is the same as the one for `For`
def preprocess_node_defun(ast_node, irFileGen, config):
    ## TODO: For now we don't want to compile function bodies
    # preprocessed_body = preprocess_close_node(ast_node.body, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    # ast_node.body = preprocessed_body
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=False)
    return preprocessed_ast_object

## TODO: If the preprocessed is not maximal we actually need to combine it with the one on the right.
def preprocess_node_semi(ast_node, irFileGen, config):
    # preprocessed_left, should_replace_whole_ast, is_non_maximal = preprocess_node(ast_node.left, irFileGen, config)
    preprocessed_left, sth_replaced_left = preprocess_close_node(ast_node.left_operand, irFileGen, config)
    preprocessed_right, sth_replaced_right = preprocess_close_node(ast_node.right_operand, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.left_operand = preprocessed_left
    ast_node.right_operand = preprocessed_right
    sth_replaced = sth_replaced_left or sth_replaced_right
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=sth_replaced)
    return preprocessed_ast_object

def preprocess_node_and(ast_node, irFileGen, config):
    # preprocessed_left, should_replace_whole_ast, is_non_maximal = preprocess_node(ast_node.left, irFileGen, config)
    preprocessed_left, sth_replaced_left = preprocess_close_node(ast_node.left_operand, irFileGen, config)
    preprocessed_right, sth_replaced_right = preprocess_close_node(ast_node.right_operand, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.left_operand = preprocessed_left
    ast_node.right_operand = preprocessed_right
    sth_replaced = sth_replaced_left or sth_replaced_right
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=sth_replaced)
    return preprocessed_ast_object

def preprocess_node_or(ast_node, irFileGen, config):
    # preprocessed_left, should_replace_whole_ast, is_non_maximal = preprocess_node(ast_node.left, irFileGen, config)
    preprocessed_left, sth_replaced_left = preprocess_close_node(ast_node.left_operand, irFileGen, config)
    preprocessed_right, sth_replaced_right = preprocess_close_node(ast_node.right_operand, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.left_operand = preprocessed_left
    ast_node.right_operand = preprocessed_right
    sth_replaced = sth_replaced_left or sth_replaced_right
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=sth_replaced)
    return preprocessed_ast_object

def preprocess_node_not(ast_node, irFileGen, config):
    # preprocessed_left, should_replace_whole_ast, is_non_maximal = preprocess_node(ast_node.left, irFileGen, config)
    preprocessed_body, sth_replaced = preprocess_close_node(ast_node.body, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.body = preprocessed_body
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=sth_replaced)
    return preprocessed_ast_object


def preprocess_node_if(ast_node, irFileGen, config):
    # preprocessed_left, should_replace_whole_ast, is_non_maximal = preprocess_node(ast_node.left, irFileGen, config)
    preprocessed_cond, sth_replaced_cond = preprocess_close_node(ast_node.cond, irFileGen, config)
    preprocessed_then, sth_replaced_then = preprocess_close_node(ast_node.then_b, irFileGen, config)
    preprocessed_else, sth_replaced_else = preprocess_close_node(ast_node.else_b, irFileGen, config)
    ## TODO: Could there be a problem with the in-place update
    ast_node.cond = preprocessed_cond
    ast_node.then_b = preprocessed_then
    ast_node.else_b = preprocessed_else
    sth_replaced = sth_replaced_cond or sth_replaced_then or sth_replaced_else
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=sth_replaced)
    return preprocessed_ast_object

def preprocess_case(case, irFileGen, config):
    preprocessed_body, sth_replaced = preprocess_close_node(case["cbody"], irFileGen, config)
    case["cbody"] = preprocessed_body
    return case, sth_replaced

def preprocess_node_case(ast_node, irFileGen, config):
    preprocessed_cases_replaced = [preprocess_case(case, irFileGen, config) for case in ast_node.cases]
    preprocessed_cases, sth_replaced_cases = list(zip(*preprocessed_cases_replaced))
    ## TODO: Could there be a problem with the in-place update
    ast_node.cases = preprocessed_cases
    preprocessed_ast_object = PreprocessedAST(ast_node,
                                              replace_whole=False,
                                              non_maximal=False,
                                              something_replaced=any(sth_replaced_cases))
    return preprocessed_ast_object


## TODO: I am a little bit confused about how compilation happens.
##       Does it happen bottom up or top down: i.e. when we first encounter an occurence
##       do we recurse in it and then compile from the leaf, or just compile the surface?



## Replaces IR subtrees with a command that calls them (more
## precisely, a command that calls a python script to call them).
##
## Note: The traversal that replace_irs does, is exactly the same as
## the one that is done by compile_node. Both of these functions
## transform nodes of type t to something else.
##
## TODO: For now this just replaces the IRs starting from the ourside
## one first, but it should start from the bottom up to handle
## recursive IRs.

## This function serializes a candidate df_region in a file, and in its place,
## it adds a command that calls our distribution planner with the name of the
## saved file.
def replace_df_region(asts, irFileGen, config, ast_text=None):
    _, ir_filename = ptempfile()

    ## Serialize the node in a file
    with open(ir_filename, "wb") as ir_file:
        pickle.dump(asts, ir_file)

    ## Serialize the candidate df_region asts back to shell
    ## so that the sequential script can be run in parallel to the compilation.
    _, sequential_script_file_name = ptempfile()
    ## If we don't have the original ast text, we need to unparse the ast
    if (ast_text is None):
        kv_asts = [ast_node_to_untyped_deep(ast) for ast in asts]
        from_ast_objects_to_shell_file(kv_asts, sequential_script_file_name)
    else:
        ## However, if we have the original ast text, then we can simply output that.
        with open(sequential_script_file_name, "w") as script_file:
            script_file.write(ast_text)

    ## Replace it with a command that calls the distribution
    ## planner with the name of the file.
    replaced_node = make_call_to_runtime(ir_filename, sequential_script_file_name)

    return replaced_node

## This function makes a command that calls the pash runtime
## together with the name of the file containing an IR. Then the
## pash runtime should read from this file and continue
## execution.
##
## TODO: At the moment this is written in python but it is in essense a simple shell script.
##       Is it possible to make it be a simple string instead of manually creating the AST?
##
## (MAYBE) TODO: The way I did it, is by calling the parser once, and seeing
## what it returns. Maybe it would make sense to call the parser on
## the fly to have a cleaner implementation here?
def make_call_to_runtime(ir_filename, sequential_script_file_name) -> AstNode:

    ## Save the previous exit state:
    ## ```
    ## pash_previous_exit_status="$?"
    ## ```
    assignments = [["pash_previous_exit_status",
                    [make_quoted_variable("?")]]]
    previous_status_command = make_command([], assignments=assignments)

    ## Save the input arguments
    ## ```
    ## pash_input_args="$@"
    ## ```
    assignments = [["pash_input_args",
                    [make_quoted_variable("@")]]]
    input_args_command = make_command([],
                                      assignments=assignments)

    ## Call the runtime
    arguments = [string_to_argument("source"),
                 string_to_argument(config.RUNTIME_EXECUTABLE),
                 string_to_argument(sequential_script_file_name),
                 string_to_argument(ir_filename)]
    ## Pass a relevant argument to the planner
    arguments += config.pass_common_arguments(config.pash_args)
    runtime_node = make_command(arguments)

    ## Restore the arguments to propagate internal changes, e.g., from `shift` outside.
    ## ```
    ## set -- $pash_input_args
    ## ```
    ##
    ## TODO: Maybe we need to only do this if there is a change.
    set_arguments = [string_to_argument("set"),
                     string_to_argument("--"),
                     [standard_var_ast("pash_input_args")]]
    set_args_node = make_command(set_arguments)

    ## Restore the exit code (since now we have executed `set` last)
    ## ```
    ## ( exit "$pash_runtime_final_status")
    ## ```
    set_exit_status_command_arguments = [string_to_argument("exit"),
                                         [make_quoted_variable("pash_runtime_final_status")]]
    set_exit_status_command = make_command(set_exit_status_command_arguments)
    set_exit_status_node = make_kv('Subshell', [0, set_exit_status_command, []])

    sequence = make_semi_sequence([previous_status_command,
                                   input_args_command,
                                   runtime_node,
                                   set_args_node,
                                   set_exit_status_node])
    return sequence

##
## Pattern matching for the AST
##

def check_if_ast_is_supported(construct, arguments, **kwargs):
    return

def ast_match_untyped(untyped_ast_object, cases, *args):
    ## TODO: This should construct the complete AstNode object (not just the surface level)
    ## TODO: Remove this and then at some point make real proper use of the AstNode
    ast_node = AstNode(untyped_ast_object)
    if ast_node.construct is AstNodeConstructor.PIPE:
        ast_node.check(children_count = lambda : len(ast_node.items) >= 2)
    return ast_match(ast_node, cases, *args)

def ast_match(ast_node, cases, *args):
    ## TODO: Remove that once `ast_match_untyped` is fixed to
    ##       construct the whole AstNode object.
    if(not isinstance(ast_node, AstNode)):
        return ast_match_untyped(ast_node, cases, *args)

    return cases[ast_node.construct.value](*args)(ast_node)
