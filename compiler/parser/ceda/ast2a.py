# import os;
import sys;
from dash2 import *;


# parser.h
CTLESC       = 129;
CTLVAR       = 130;
CTLENDVAR    = 131;
CTLBACKQ     = 132;
CTLARI       = 134;
CTLENDARI    = 135;
CTLQUOTEMARK = 136;

# Internal use only
STACK_CTLVAR = 100;
STACK_CTLARI = 101;
STACK_CTLQUO = 102;


VAR_TYPES \
    = [
       "Normal",   # 0x0
       "UNUSED",
       "Minus",    # 0x2
       "Plus",     # 0x3
       "Question", # 0x4
       "Assign",   # 0x5
       "TrimR",    # 0x6
       "TrimRMax", # 0x7
       "TrimL",    # 0x8
       "TrimLMax", # 0x9
       "Length"    # 0xa
      ];


SKIP_COMMAND = ["Command", [-1, [], [], []]];

ORD_TILDE  = ord ('~');
ORD_EQUALS = ord ('=');
ORD_MINUS  = ord ('-');
ORD_COLON  = ord (':');
ORD_SLASH  = ord ('/');


def var_type (i):
    return VAR_TYPES [i];


# Inline 'list (map (of_node, nodelist (nl)))'
def map_ofnode_nodelist (nl):
    snek = [];

    # ctypes has different semantics for POINTER vs. c_void_p
    # See https://groups.google.com/g/nzpug/c/5CJxaWjuQro
    while (nl):
        snek.append (of_node (nl.contents.n));
        nl = nl.contents.next;

    return snek;


def of_node (n_ptr):
    if (not n_ptr):
        return SKIP_COMMAND;
    else:
        n = n_ptr.contents;

#        print ("");
#        print ("###" + str (n.type));
#        print ("");

        # 4412 0 NCMD
        # 2442 7 NSEMI
        # 517 8  NIF
        # 255 12 NCASE
        # 252 5  NAND
        # 152 6  NOR
        # 126 11 NFOR
        # 119 14 NDEFUN
        # 107 1  NPIPE
        # 16 4   NSUBSHELL
        # 14 9   NWHILE
        # 4 2    NREDIR
        # 2 10   NUNTIL

        if (n.type == NCMD):
            return (["Command",
                     [n.ncmd.linno,
                      to_assigns (n.ncmd.assign),
                      to_args (n.ncmd.args),
                      redirs (n.ncmd.redirect)]]);
        elif (n.type == NSEMI):
            return ["Semi", of_binary (n)];
        elif (n.type == NIF):
            return (["If",
                     [of_node (n.nif.test),
                      of_node (n.nif.ifpart),
                      of_node (n.nif.elsepart)]]);
        elif (n.type == NCASE):
            cases_hashes = []; # Poetic

            for case in caselist (n.ncase.cases):
                (pattern, body) = case;

                current_case \
                    = {'cpattern' : to_args (pattern),
                       'cbody'    : of_node (body)};

                cases_hashes.append (current_case);

            return (["Case",
                     [n.ncase.linno,
                      to_arg (n.ncase.expr.contents.narg),
                      cases_hashes]]);
        elif (n.type == NAND):
            return ["And", of_binary (n)];
        elif (n.type == NOR):
            return ["Or", of_binary (n)];
        elif (n.type == NFOR):
            return ["For",
                    [n.nfor.linno,
                     to_args (n.nfor.args),
                     of_node (n.nfor.body),
                     n.nfor.var.decode ("charmap")]];
        elif (n.type == NDEFUN):
            return ["Defun",
                    [n.ndefun.linno,
                     n.ndefun.text.decode ("charmap"),
                     of_node (n.ndefun.body)]];
        elif (n.type == NPIPE):
            return (["Pipe",
                     [n.npipe.backgnd != 0,
                      map_ofnode_nodelist (n.npipe.cmdlist)]]);
                     # list (map (of_node, nodelist (n.npipe.cmdlist)))]]);
        elif (n.type == NSUBSHELL):
            return ["Subshell", of_nredir (n)];
        elif (n.type == NWHILE):
            return ["While", of_binary (n)];
        elif (n.type == NREDIR):
            return ["Redir", of_nredir (n)];
        elif (n.type == NUNTIL):
            (t, b) = of_binary (n);
            return ["While", [["Not", t], b]];

        elif (n.type == NBACKGND):
            return ["Background", of_nredir (n)];
        elif (n.type == NNOT):
            return ["Not", of_node (n.nnot.com)];
        else:
            print ("Unexpected type");
            sys.stdout.flush ();
            os.abort ();


def of_nredir (n):
    return ([n.nredir.linno, of_node (n.nredir.n), redirs (n.nredir.redirect)]);


def mk_file (ty, n):
    arg = to_arg (n.nfile.fname.contents.narg);

    return ["File", [ty, n.nfile.fd, arg]];


def mk_dup (ty, n):
    ndup = n.ndup;
    vname = ndup.vname;

    tgt = [];

    if (not vname):
        dupfd = ndup.dupfd;
        if (dupfd == -1):
            tgt.append (["C", ORD_MINUS]);
        else:
            dupfd_str = str (dupfd);

            for i in range (len (dupfd_str)):
                tgt.append (["C", ord (dupfd_str [i])]);
    else:
        tgt = to_arg (vname.narg);

    return (["Dup", [ty, ndup.fd, tgt]]);


def mk_here (ty, n):
    return ["Heredoc", [ty, n.nhere.fd, to_arg (n.nhere.doc.contents.narg)]];


def redirs (n_ptr):
    rlist = [];

    while (n_ptr):
        h = [];

        n = n_ptr.contents;

        if (n.type == NTO):
            h = mk_file ("To", n);
        elif (n.type == NCLOBBER):
            h = mk_file ("Clobber", n);
        elif (n.type == NFROM):
            h = mk_file ("From", n);
        elif (n.type == NFROMTO):
            h = mk_file ("FromTo", n);
        elif (n.type == NAPPEND):
            h = mk_file ("Append", n);
        elif (n.type == NTOFD):
            h = mk_dup ("ToFD", n);
        elif (n.type == NFROMFD):
            h = mk_dup ("FromFD", n);
        elif (n.type == NHERE):
            h = mk_here ("Here", n);
        elif (n.type == NXHERE):
            h = mk_here ("XHere", n);
        else:
            print ("unexpected node_type in redirlist");
            os.abort ();

        rlist.append (h);

        n_ptr = n.nfile.next;

    return rlist;


def of_binary (n):
    return [of_node (n.nbinary.ch1), of_node (n.nbinary.ch2)];


def to_arg (narg):
    s = explode_rev (narg.text);
    bqlist = narg.backquote;
    stack = [];

    a = parse_arg (s, bqlist, stack);

    assert (len (s) == 0);
    # assert (nullptr bqlist)
#    if (bqlist):
#        print ("bqlist is not null");
#        print (bqlist);
#        os.abort ();
    assert (len (stack) == 0);

    return (a);


def parse_arg (s, bqlist, stack):
    acc = [];

    while (True):
        s_len = len (s);
        # stack_len = len (stack);

        # | [],[] -> [],[],bqlist,[]
        if ((s_len == 0) and (len (stack) == 0)):
            return (acc);
        # | [],`CTLVar::_ -> failwith "End of string before CTLENDVAR"

        elif (s_len == 0): # We know that len (stack) > 0!
            if (stack [-1] == STACK_CTLVAR):
                print ("End of string before CTLENDVAR");
                os.abort ();
            # | [],`CTLAri::_ -> failwith "End of string before CTLENDARI"
            elif (stack [-1] == STACK_CTLARI):
                print (s);
                print (stack);

                print ("End of string before CTLENDARI");
                os.abort ();
            # | [],`CTLQuo::_ -> failwith "End of string before CTLQUOTEMARK"
            elif (stack [-1] == STACK_CTLQUO):
                print (s);
                print (stack);

                print ("End of string before CTLENDQUOTEMARK");
                os.abort ();
            else:
                print ("Invalid stack");
                os.abort ();

        else: # We know that len (s) > 0
            # (* CTLESC *)
            # | '\129'::c::s,_ -> arg_char (E c) s bqlist stack
            if ((s_len >= 2) and (s [-1] == CTLESC)):
                s.pop ();
                c = s.pop ();

                acc.append (["E", c]);

            # (* CTLVAR *)
            # | '\130'::t::s,_ ->
            elif ((s_len >= 2) and (s [-1] == CTLVAR)):
                s.pop ();
                t = s.pop ();

                # let var_name,s = split_at (fun c -> c = '=') s in
                var_name = "";
                while ((len (s) > 0) and (s [-1] != ORD_EQUALS)):
                    c = s.pop ();
                    var_name = var_name + chr (c);

                v = [];

                if (((t & 0xf) == 0x1) and (len (s) >= 1) and (s [-1] == ORD_EQUALS)):
                    s.pop ();

                    v = ["V", ["Normal", False, var_name, []]];
                elif (((t & 0xf) == 0xa) and (len (s) >= 2) and (s [-1] == ORD_EQUALS) and (s [-2] == 131)):
                    s.pop ();
                    s.pop ();

                    v = ["V", ["Length", False, var_name, []]];
                elif ((((t & 0xf) == 0x1) or ((t & 0xf) == 0xa)) and (len (s) >= 1)):
                    print ("Missing CTLENDVAR for VSNORMAL/VSLENGTH");
                    os.abort ();
                elif ((len (s) >= 1) and (s [-1] == ORD_EQUALS)):
                    s.pop ();

                    vstype = t & 0xf;

                    stack.append (STACK_CTLVAR);

                    a = parse_arg (s, bqlist, stack);

                    v = ["V", [var_type (vstype), (t & 0x10 == 0x10), var_name, a]];
                elif (len (s) >= 1):
                    print (s);
                    print (stack);

                    print ("Expected '=' terminating variable name");
                    os.abort ();
                elif (len (s) == 0):
                    print ("Expected '=' terminating variable name, found EOF");
                    os.abort ();
                else:
                    print ("This shouldn't be reachable");
                    os.abort ();

                acc.append (v);

            # | '\130'::_, _ -> raise (ParseException "bad substitution (missing variable name in ${}?")
            elif (False and (s [-1] == CTLVAR)): # Disable to match PaSH's version of libdash
                print (s);
                print (stack);

                print ("bad substitution (missing variable name in ${}?");
                os.abort ();

            # (* CTLENDVAR *)
            # | '\131'::s,`CTLVar::stack' -> [],s,bqlist,stack'
            elif (s [-1] == CTLENDVAR):
                if (len (stack) >= 1):
                    if (stack [-1] == STACK_CTLVAR):
                        s.pop ();
                        stack.pop ();

                        return (acc);
                    # | '\131'::_,`CTLAri::_ -> failwith "Saw CTLENDVAR before CTLENDARI"
                    elif (stack [-1] == STACK_CTLARI):
                        print ("Saw CTLENDVAR before CTLENDARI");
                        os.abort ();
                    # | '\131'::_,`CTLQuo::_ -> failwith "Saw CTLENDVAR before CTLQUOTEMARK"
                    elif (stack [-1] == STACK_CTLQUO):
                        print ("Saw CTLENDVAR before CTLQUOTEMARK");
                        os.abort ();
                    # | '\131'::_,[] -> failwith "Saw CTLENDVAR outside of CTLVAR"
                else:
                    print ("Saw CTLENDVAR outside of CTLVAR");
                    os.abort ();

            # (* CTLBACKQ *)
            # | '\132'::s,_ ->
            elif (s [-1] == CTLBACKQ):
                s.pop ();

                if (not bqlist):
                    print (bqlist);
                    print ("Saw CTLBACKQ but bqlist was null");
                    os.abort ();
                else:
                    acc.append (["B", of_node (bqlist.contents.n)]);

                    bqlist = bqlist.contents.next;

            # (* CTLARI *)
            # | '\134'::s,_ ->
            elif (s [-1] == CTLARI):
                s.pop ();

                stack.append (STACK_CTLARI);

                a = parse_arg (s, bqlist, stack);

                # TODO: assert (stack = stack');

                acc.append (["A", a]);

            # (* CTLENDARI *)
            # | '\135'::s,`CTLAri::stack' -> [],s,bqlist,stack'
            elif (s [-1] == CTLENDARI):
                if (len (stack) >= 1):
                    if (stack [-1] == STACK_CTLARI):
                        s.pop ();
                        stack.pop ();

                        return (acc);
                    # | '\135'::_,`CTLVar::_' -> failwith "Saw CTLENDARI before CTLENDVAR"
                    elif (stack [-1] == STACK_CTLVAR):
                        print ("Saw CTLENDARI before CTLENDVAR");
                        os.abort ();
                    # | '\135'::_,`CTLQuo::_' -> failwith "Saw CTLENDARI before CTLQUOTEMARK"
                    elif (stack [-1] == STACK_CTLQUO):
                        print ("Saw CTLENDARI before CTLQUOTEMARK");
                        os.abort ();
                    # | '\135'::_,[] -> failwith "Saw CTLENDARI outside of CTLARI"
                else:
                    print ("Saw CTLENDARI outside of CTLARI");
                    os.abort ();

            # (* CTLQUOTEMARK *)
            # | '\136'::s,`CTLQuo::stack' -> [],s,bqlist,stack'
            elif (s [-1] == CTLQUOTEMARK):
                if ((len (stack) >= 1) and (stack [-1] == STACK_CTLQUO)):
                    s.pop ();
                    stack.pop ();

                    return (acc);
                # | '\136'::s,_ ->
                else:
                    s.pop ();
                    stack.append (STACK_CTLQUO);

                    a = parse_arg (s, bqlist, stack);

                    acc.append (["Q", a]);

            # (* tildes *)
            # | '~'::s,stack ->
            elif (s [-1] == ORD_TILDE):
                s.pop ();

                if ((STACK_CTLQUO in stack) or (STACK_CTLARI in stack)):
                    acc.append (["C", ORD_TILDE]);
                else:
                    uname = parse_tilde (s);

                    acc.append (["T", uname]);

            # (* ordinary character *)
            # | c::s,_ -> arg_char (C c) s bqlist stack
            else:
                c = s.pop ();

                acc.append (["C", c]);


def stringOrNull (acc_str):
    if (acc_str == ""):
        return "None";
    else:
        return ["Some", acc_str];


def parse_tilde (s):
    acc_str = "";

    while (True):
        if (s == []):
            return stringOrNull (acc_str);
        else:
            s_last = s [-1];

            if (s_last == CTLESC):
                return ("None");
            elif (s_last == CTLQUOTEMARK):
                return ("None");
            elif (s_last == CTLENDVAR):
                return (stringOrNull (acc_str));
            elif (s_last == ORD_COLON):
                return (stringOrNull (acc_str));
            elif (s_last == ORD_SLASH):
                return (stringOrNull (acc_str));
            else:
                c = s.pop ();
                acc_str = acc_str + chr (c);


def to_assign (a_rev):
    v_str = "";

    while (len (a_rev) > 0):
        if (a_rev [-1][0] != 'C'):
            print ("Unexpected special character in assignment");
            sys.stdout.flush ();
            os.abort ();

        if (a_rev [-1][1] == ORD_EQUALS):
            a_rev.pop ();

            a_rev.reverse ();
            return (v_str, a_rev);

            # return (v_str, reversed (a_rev));
        else:
            c = a_rev [-1][1];
            a_rev.pop ();

            v_str = v_str + chr (c);

    print ("Never found an '=' sign in assignment");
    os.abort ();


# Inlined to_args
# to_assigns n = List.map (to_assign []) (to_args n)
def to_assigns (n):
    assigns = [];

    while (n):
        if (n.contents.type != NARG):
            print ("Unexpected type: " + n.contents.type);
            sys.stdout.flush ();
            os.abort ();

        arg = to_arg (n.contents.narg);

        arg.reverse ();
        assigns.append (to_assign (arg));

        n = n.contents.narg.next;

    return (assigns);


# to_assigns n = List.map (to_assign []) (to_args n)
def to_assigns_classic (n):
    assigns = []

    for a in (to_args (n)):
        a.reverse ();
        assigns.append (to_assign (a));

    return (assigns);


def to_args (n):
    snek = [];

    # ctypes has different semantics for POINTER vs. c_void_p
    # See https://groups.google.com/g/nzpug/c/5CJxaWjuQro
    while (n):
        if (n.contents.type != NARG):
            print ("Unexpected type: " + n.contents.type);
            sys.stdout.flush ();
            os.abort ();

        arg = to_arg (n.contents.narg);
        snek.append (arg);

        n = n.contents.narg.next;

    return snek;
