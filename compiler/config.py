import json
import os
import subprocess
import yaml

from ir_utils import *

## Global
__version__ = "0.2" # FIXME add libdash version
GIT_TOP_CMD = [ 'git', 'rev-parse', '--show-toplevel', '--show-superproject-working-tree']
if 'PASH_TOP' in os.environ:
    PASH_TOP = os.environ['PASH_TOP']
else:
    PASH_TOP = subprocess.run(GIT_TOP_CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout.rstrip()

PARSER_BINARY = os.path.join(PASH_TOP, "compiler/parser/parse_to_json.native")
PRINTER_BINARY = os.path.join(PASH_TOP, "compiler/parser/json_to_shell.native")

PYTHON_VERSION = "python3"
PLANNER_EXECUTABLE = os.path.join(PASH_TOP, "compiler/pash_runtime.py")
RUNTIME_EXECUTABLE = os.path.join(PASH_TOP, "compiler/pash_runtime.sh")

PASH_TMP_PREFIX = "pash_"

config = {}
annotations = []
pash_args = None

def load_config(config_file_path=""):
    global config
    pash_config = {}
    CONFIG_KEY = 'distr_planner'

    if(config_file_path == ""):
      config_file_path = '{}/compiler/config.yaml'.format(PASH_TOP)
    with open(config_file_path) as config_file:
        pash_config = yaml.load(config_file, Loader=yaml.FullLoader)

    if not pash_config:
        raise Exception('No valid configuration could be loaded from {}'.format(config_file_path))

    if CONFIG_KEY not in pash_config:
        raise Exception('Missing `{}` config in {}'.format(CONFIG_KEY, config_file_path))

    config = pash_config

## These are arguments that are common to pash.py and pash_runtime.py
def add_common_arguments(parser):
    parser.add_argument("-w", "--width",
                        type=int,
                        default=2, 
                        help="set data-parallelism factor")

    parser.add_argument("--no_optimize",
                        help="not apply transformations over the DFG",
                        action="store_true")
    parser.add_argument("--dry_run_compiler",
                        help="not execute the compiled script, even if the compiler succeeded",
                        action="store_true")
    parser.add_argument("--assert_compiler_success",
                        help="assert that the compiler succeeded (used to make tests more robust)",
                        action="store_true")
    parser.add_argument("-t", "--output_time", #FIXME: --time
                        help="output the time it took for every step",
                        action="store_true") 
    parser.add_argument("-p", "--output_optimized", # FIXME: --print
                        help="output the parallel shell script for inspection",
                        action="store_true")
    parser.add_argument("-d", "--debug", 
                        help="configure debug level; defaults to 0",
                        default="0")
    parser.add_argument("--log_file", 
                        help="configure where to write the log; defaults to stderr.",
                        default="")
    parser.add_argument("--no_eager",
                        help="disable eager nodes before merging nodes",
                        action="store_true")
    parser.add_argument("--speculation",
                        help="run the original script during compilation; if compilation succeeds, abort the original and run only the parallel (quick_abort) (Default: no_spec)",
                        choices=['no_spec', 'quick_abort'],
                        default='no_spec')
    parser.add_argument("--termination",
                        help="determine the termination behavior of the DFG. Defaults to cleanup after the last process dies, but can drain all streams until depletion",
                        choices=['clean_up_graph', 'drain_stream'],
                        default="clean_up_graph")
    parser.add_argument("--config_path",
                        help="determines the config file path. By default it is 'PASH_TOP/compiler/config.yaml'.",
                        default="")
    parser.add_argument("-v", "--version",
                        action='version',
                        version='%(prog)s {version}'.format(version=__version__))
    return

def pass_common_arguments(pash_arguments):
    arguments = []
    if (pash_arguments.no_optimize):
        arguments.append(string_to_argument("--no_optimize"))
    if (pash_arguments.dry_run_compiler):
        arguments.append(string_to_argument("--dry_run_compiler"))
    if (pash_arguments.assert_compiler_success):
        arguments.append(string_to_argument("--assert_compiler_success"))
    if (pash_arguments.output_time):
        arguments.append(string_to_argument("--output_time"))
    if (pash_arguments.output_optimized):
        arguments.append(string_to_argument("--output_optimized"))
    if(not pash_arguments.log_file == ""):
        arguments.append(string_to_argument("--log_file"))
        arguments.append(string_to_argument(pash_arguments.log_file))
    if (pash_arguments.no_eager):
        arguments.append(string_to_argument("--no_eager"))
    arguments.append(string_to_argument("--debug"))
    arguments.append(string_to_argument(pash_arguments.debug))
    arguments.append(string_to_argument("--termination"))
    arguments.append(string_to_argument(pash_arguments.termination))
    arguments.append(string_to_argument("--speculation"))
    arguments.append(string_to_argument(pash_arguments.speculation))
    arguments.append(string_to_argument("--width"))
    arguments.append(string_to_argument(str(pash_arguments.width)))
    if(not pash_arguments.config_path == ""):
        arguments.append(string_to_argument("--config_path"))
        arguments.append(string_to_argument(pash_arguments.config_path))
    return arguments

def init_log_file():
    global pash_args
    if(not pash_args.log_file == ""):
        with open(pash_args.log_file, "w") as f:
            pass

##
## Read a shell variables file
##

def read_vars_file(var_file_path):
    global config

    config['shell_variables'] = None
    config['shell_variables_file_path'] = var_file_path
    if(not var_file_path is None):
        vars_dict = {}
        with open(var_file_path) as f:
            lines = [line.rstrip() for line in f.readlines()]

        for line in lines:
            words = line.split(' ')
            _export_or_typeset = words[0]
            rest = " ".join(words[1:])

            space_index = rest.find(' ')
            eq_index = rest.find('=')
            var_type = None
            ## This means we have a type
            if(space_index < eq_index and not space_index == -1):
                var_type = rest[:space_index]
                rest = rest[(space_index+1):]
                eq_index = rest.find('=')
            ## We now find the name and value
            var_name = rest[:eq_index] 
            var_value = rest[(eq_index+1):]

            vars_dict[var_name] = (var_type, var_value)

        config['shell_variables'] = vars_dict


# TODO load command class file path from config
command_classes_file_path = '{}/compiler/command-classes.yaml'.format(PASH_TOP)
command_classes = {}
with open(command_classes_file_path) as command_classes_file:
    command_classes = yaml.load(command_classes_file, Loader=yaml.FullLoader)

if not command_classes:
    raise Exception('Failed to load description of command classes from {}'.format(command_classes_file_path))

stateless_commands = command_classes['stateless'] if 'stateless' in command_classes else {}
pure_commands = command_classes['pure'] if 'pure' in command_classes else {}
parallelizable_pure_commands = command_classes['parallelizable_pure'] if 'parallelizable_pure' in command_classes else {}

## TODO: Move these to a configuration file
bigram_g_map_num_outputs = 3
