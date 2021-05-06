import os
import sys
import subprocess
from ctypes import *

from ast2a import of_node
from dash2 import *

if 'PASH_TOP' in os.environ:
    PASH_TOP = os.environ['PASH_TOP']
else:
    GIT_TOP_CMD = [ 'git', 'rev-parse', '--show-toplevel', '--show-superproject-working-tree']
    PASH_TOP = subprocess.run(GIT_TOP_CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout.rstrip()


# TODO: use Pash root directory
LIBDASH_LIBRARY_PATH = os.path.join(PASH_TOP, "compiler/parser/libdash/src/.libs/libdash.so")


EOF_NLEFT = -99; # libdash/src/input.c


# This is a mix of dash.ml:parse_next and parse_to_json.ml.
def parse_to_ast (inputPath, init=True):
    lines = [];

    libdash = CDLL (LIBDASH_LIBRARY_PATH);

    if (init):
        initialize (libdash);

    if (inputPath == "-"):
        setinputtostdin (libdash);
    else:
        setinputfile (libdash, inputPath);

        fp = open (inputPath, 'r');
        for line in fp:
            lines.append (line);
        fp.close()

    # struct parsefile *parsefile = &basepf;  /* current input file */
    # Get the value of parsefile (not &parsefile)!
    parsefile_ptr_ptr = addressof (parsefile.in_dll (libdash, "parsefile"));
    parsefile_ptr = cast (parsefile_ptr_ptr, POINTER (POINTER (parsefile)));
    parsefile_var = parsefile_ptr.contents;

    smark = init_stack (libdash);

    NEOF = addressof (c_int.in_dll (libdash, "tokpushback"));
    NERR = addressof (c_int.in_dll (libdash, "lasttoken"));

    while (True):
        linno_before = parsefile_var.contents.linno - 1; # libdash is 1-indexed

        n_ptr_C = parsecmd_safe (libdash, False);

        linno_after = parsefile_var.contents.linno - 1; # libdash is 1-indexed
        nleft_after = parsefile_var.contents.nleft;

        if (n_ptr_C == None): # Dash.Null
            pass;
        elif (n_ptr_C == NEOF): # Dash.Done
            break;
        elif (n_ptr_C == NERR): # Dash.Error
            break;
        else:
            if (nleft_after == EOF_NLEFT):
                linno_after = linno_after + 1; # The last line wasn't counted

                if (inputPath != "-"):
                    ## Both of these assertions check "our" assumption with respect to the final parser state
                    ## and are therefore not necessary if they become an issue.
                    assert((linno_after == len (lines)) or (linno_after == len (lines) + 1))

                    # Last line did not have a newline
                    assert(len (lines [-1]) > 0 and (lines [-1][-1] != '\n'))
            else:
                assert (nleft_after == 0); # Read whole lines

            n_ptr = cast (n_ptr_C, POINTER (union_node));
            new_ast = of_node (n_ptr);

            if (inputPath != "-"):
                parsedLines = "".join (lines [linno_before:linno_after]);
            else:
                parsedLines = "# Cannot return parsed lines for stdin input";

            yield (new_ast, parsedLines, linno_before, linno_after)

            pop_stack (libdash, smark);
