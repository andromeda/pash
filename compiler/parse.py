import json
import tempfile
import os
import re
import config
import subprocess
import sys

from util import *

sys.path.append(os.path.join(config.PASH_TOP, "compiler/parser/ceda"))
from parse_to_ast2 import parse_to_ast
from json_to_shell2 import json_to_shell_string

## Parses straight a shell script to an AST
## through python without calling it as an executable
def parse_shell_to_ast(input_script_path):
    new_asts = parse_to_ast(input_script_path)
    return new_asts

## TODO: Avoid going through JSON for the unparsing.
## Parser straight from JSON to a shell string without calling an executable 
def from_ir_to_shell(ir_filename):
    preprocessed_script = json_to_shell_string(ir_filename)
    return preprocessed_script

def parse_shell(input_script_path):
    if(not os.path.isfile(input_script_path)):
        log("Error! File:", input_script_path, "does not exist.", level=0)
        sys.exit(1)
    parser_output = subprocess.run([config.PARSER_BINARY, input_script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if (not parser_output.returncode == 0):
        log(parser_output.stderr)
        parser_output.check_returncode()
    return parser_output.stdout

def from_ir_to_shell_legacy(ir_filename):
    printer_output = subprocess.run([config.PRINTER_BINARY, ir_filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    printer_output.check_returncode()
    preprocessed_script = printer_output.stdout
    return preprocessed_script

def from_ir_to_shell_file(ir_filename, new_shell_filename):
    preprocessed_script = from_ir_to_shell(ir_filename)
    with open(new_shell_filename, 'w') as new_shell_file:
        new_shell_file.write(preprocessed_script)

