#!/usr/bin/python3


import os;
# from os import abort;


STRING_OF_VAR_TYPE_DICT = {
    "Normal"   : "",
    "Minus"    : "-",
    "Plus"     : "+",
    "Question" : "?",
    "Assign"   : "=",
    "TrimR"    : "%",
    "TrimRMax" : "%%",
    "TrimL"    : "#",
    "TrimLMax" : "##",
    "Length"   : "#"
};


# dash.ml
#
# let rec intercalate p ss =
#   match ss with
#   | [] -> ""
#   | [s] -> s
#   | s::ss -> s ^ p ^ intercalate p ss  
def intercalate (p, ss):
    str = p.join (ss);

#    str = "";
#
#    i = 0;
#    for s in ss:
#        if (i > 0):
#            str = str + p;
#
#        str = str + s;
#
#        i = i + 1;

    return (str);


# dash.ml
#
# let braces s = "{ " ^ s ^ " ; }"
def braces (s):
    return "{ " + s + " ; }";


# dash.ml
#
# let parens s = "( " ^ s ^ " )"
def parens (s):
    return "( " + s + " )";


# let string_of_var_type = function
#  | Normal -> ""
#  | Minus -> "-"
#  | Plus -> "+"
#  | Question -> "?"
#  | Assign -> "="
#  | TrimR -> "%"
#  | TrimRMax -> "%%"
#  | TrimL -> "#"
#  | TrimLMax -> "##" 
#  | Length -> "#" 
def string_of_var_type (var_type):
    if (var_type in STRING_OF_VAR_TYPE_DICT):
        return (STRING_OF_VAR_TYPE_DICT [var_type]);

    exit (1);


# let separated f l = intercalate " " (List.map f l)
def separated (f, l):
    return " ".join (map (f, l));


# let show_unless expected actual =
#   if expected = actual
#   then ""
#   else string_of_int actual
def show_unless (expected, actual):
    if (expected == actual):
        return "";
    else:
        return (str (actual));


# let background s = "{ " ^ s ^ " & }"
def background (s):
    return ("{ " + s + " & }");


# let rec to_string = function
#   | Command (_,assigns,cmds,redirs) ->
#      separated string_of_assign assigns ^
#      (if List.length assigns = 0 || List.length cmds = 0 then "" else " ") ^
#      separated string_of_arg cmds ^ string_of_redirs redirs
#   | Pipe (bg,ps) ->
#      let p = intercalate " | " (List.map to_string ps) in
#      if bg then background p else p
#   | Redir (_,a,redirs) ->
#      to_string a ^ string_of_redirs redirs
#   | Background (_,a,redirs) ->
#      (* we translate 
#            cmds... &
#         to
#            { cmds & }
#         this avoids issues with parsing; in particular,
#           cmd1 & ; cmd2 & ; cmd3
#         doesn't parse; it must be:
#           cmd1 & cmd2 & cmd3
#         it's a little too annoying to track "was the last thing
#         backgrounded?" so the braces resolve the issue. testing
#         indicates that they're semantically equivalent.
#       *)
#      background (to_string a ^ string_of_redirs redirs)
#   | Subshell (_,a,redirs) ->
#      parens (to_string a ^ string_of_redirs redirs)
#   | And (a1,a2) -> to_string  a1 ^ " && " ^ to_string a2
#   | Or (a1,a2) -> to_string a1 ^ " || " ^ to_string a2
#   | Not a -> "! " ^ braces (to_string a)
#   | Semi (a1,a2) -> to_string a1 ^ " ; " ^ to_string a2
#   | If (c,t,e) -> string_of_if c t e
#   | While (Not t,b) ->
#      "until " ^ to_string t ^ "; do " ^ to_string b ^ "; done "
#   | While (t,b) ->
#      "while " ^ to_string t ^ "; do " ^ to_string b ^ "; done "
#   | For (_,a,body,var) ->
#      "for " ^ var ^ " in " ^ string_of_arg a ^ "; do " ^
#      to_string body ^ "; done"
#   | Case (_,a,cs) ->
#      "case " ^ string_of_arg a ^ " in " ^
#      separated string_of_case cs ^ " esac"
#   | Defun (_,name,body) -> name ^ "() {\n" ^ to_string body ^ "\n}"
def to_string (ast):
    # print (ast);

    if (len (ast) == 0):
        pass;
    else:
        (type, params) = ast;

        if (type == "Command"):
            (_, assigns, cmds, redirs) = params;
            str = separated (string_of_assign, assigns);
            if ((len (assigns) == 0) or (len (cmds) == 0)):
                pass;
            else:
                str += " ";
            str += separated (string_of_arg, cmds) + string_of_redirs (redirs);

            return (str);
        elif (type == "Pipe"):
            (bg, ps) = params;
            p = intercalate (" | ", (map (to_string, ps)));

            if (bg):
                return (background (p));
            else:
                return (p);
        elif (type == "Redir"):
            (_, a, redirs) = params;

            return to_string (a) + string_of_redirs (redirs);
        elif (type == "Background"):
            (_, a, redirs) = params;

            return background (to_string (a) + string_of_redirs (redirs));
        elif (type == "Subshell"):
            (_, a, redirs) = params;

            return parens (to_string (a) + string_of_redirs (redirs));
        elif (type == "And"):
            (a1, a2) = params

            return braces(to_string(a1)) + " && " + braces(to_string(a2))
        elif (type == "Or"):
            (a1, a2) = params

            return braces(to_string(a1)) + " || " + braces(to_string(a2))
        elif (type == "Not"):
            (a) = params

            return "! " + braces(to_string(a))
        elif (type == "Semi"):
            (a1, a2) = params

            return braces(to_string(a1)) + " \n " + braces(to_string(a2))
        elif (type == "If"):
            (c, t, e) = params;
            return string_of_if (c, t, e);
        elif (type == "While"):
            (first, b) = params;

            if (first [0] == "Not"):
                (_, t) = first;

                return "until " + to_string (t) + "; do " + to_string (b) + "; done ";
            else:
                t = first;

                return "while " + to_string (t) + "; do " + to_string (b) + "; done ";
        elif (type == "For"):
            (_, a, body, var) = params;

            return "for " + var + " in " + separated (string_of_arg, a) + "; do " + \
                   to_string (body) + "; done";
        elif (type == "Case"):
            (_, a, cs) = params;

            return "case " + string_of_arg (a) + " in " + \
                   separated (string_of_case, cs) + " esac";
            abort ();
        elif (type == "Defun"):
            (_, name, body) = params;

            return name + "() {\n" + to_string (body) + "\n}";
        else:
            print ("Invalid type: %s" % type);
            abort ();


# and string_of_if c t e =
#   "if " ^ to_string c ^
#   "; then " ^ to_string t ^
#   (match e with
#    | Command (-1,[],[],[]) -> "; fi" (* one-armed if *)
#    | If (c,t,e) -> "; el" ^ string_of_if c t e
#    | _ -> "; else " ^ to_string e ^ "; fi")
def string_of_if (c, t, e):
    str1 = "if " + to_string (c) + \
           "; then " + to_string (t);

    # ['Command', [-1, [], [], []]]
    if (    (len (e) == 2)        \
        and (e [0] == "Command")  \
        and (len (e [1]) == 4)    \
        and (e [1][0] == -1))     \
        and (len (e [1][1]) == 0) \
        and (len (e [1][2]) == 0) \
        and (len (e [1][3]) == 0):
       str1 = str1 + "; fi";
    elif (    e [0] == "If" \
          and (len (e [1]) == 3)):
        (c2, t2, e2) = e [1];

        str1 += "; el" + string_of_if (c2, t2, e2);
    else:
        str1 += "; else " + to_string (e) + "; fi";

    return (str1);


# https://github.com/ocaml/ocaml/blob/trunk/stdlib/char.ml
# let escaped = function
#   | '\'' -> "\\'"
#   | '\\' -> "\\\\"
#   | '\n' -> "\\n"
#   | '\t' -> "\\t"
#   | '\r' -> "\\r"
#   | '\b' -> "\\b"
#   | ' ' .. '~' as c ->
#       let s = bytes_create 1 in
#       bytes_unsafe_set s 0 c;
#       unsafe_to_string s
#   | c ->
#       let n = code c in
#       let s = bytes_create 4 in
#       bytes_unsafe_set s 0 '\\';
#       bytes_unsafe_set s 1 (unsafe_chr (48 + n / 100));
#       bytes_unsafe_set s 2 (unsafe_chr (48 + (n / 10) mod 10));
#       bytes_unsafe_set s 3 (unsafe_chr (48 + n mod 10));
#       unsafe_to_string s
def escaped (param):
    char = chr (param)

    if (char == "'"):
        return "\\'";
    elif (char == "\\"):
        return "\\\\";
    elif (char == "\n"):
        return "\\n";
    elif (char == "\t"):
        return "\\t";
    elif (char == "\r"):
        return "\\r";
    elif (char == "\b"):
        return "\\b";
    elif ((param >= ord (' ')) and (param <= ord ('~'))):
        return char;
    else:
#        str1 =   "\\" \
#               + chr (48 + int (param / 100)) \
#               + chr (48 + ((int (param / 10)) % 10)) \
#               + chr (48 + (param % 10));
        return ("\\" + str (param));


# and string_of_arg_char = function
#   | E '\'' -> "\\'"
#   | E '\"' -> "\\\""
#   | E '(' -> "\\("
#   | E ')' -> "\\)"
#   | E '{' -> "\\{"
#   | E '}' -> "\\}"
#   | E '$' -> "\\$"
#   | E '!' -> "\\!"
#   | E '&' -> "\\&"
#   | E '|' -> "\\|" 
#   | E ';' -> "\\;" 
#   | C c -> String.make 1 c
#   | E c -> Char.escaped c
#   | T None -> "~"
#   | T (Some u) -> "~" ^ u
#   | A a -> "$((" ^ string_of_arg a ^ "))"
#   | V (Length,_,name,_) -> "${#" ^ name ^ "}"
#   | V (vt,nul,name,a) ->
#      "${" ^ name ^ (if nul then ":" else "") ^ string_of_var_type vt ^ string_of_arg a ^ "}"
#   | Q a -> "\"" ^ string_of_arg a ^ "\""
#   | B t -> "$(" ^ to_string t ^ ")"
def string_of_arg_char (c):
    (type, param) = c;

    if (type == "E"):
        char = chr (param);

        if (char == "'"):
            return "\\'";
        elif (char == "\""):
            return "\\\"";
        elif (char == "("):
            return "\\(";
        elif (char == ")"):
            return "\\)";
        elif (char == "{"):
            return "\\{";
        elif (char == "}"):
            return "\\}";
        elif (char == "$"):
            return "\\$";
        elif (char == "!"):
            return "\\!";
        elif (char == "&"):
            return "\\&";
        elif (char == "|"):
            return "\\|";
        elif (char == ";"):
            return "\\;";
        else:
            return escaped (param)
    elif (type == "C"):
        return chr (param);
    elif (type == "T"):
        if (param == "None"):
            return "~";
        elif (len (param) == 2):
            if (param [0] == "Some"):
                (_, u) = param;

                return "~" + u;
            else:
                abort ();
        else:
            print ("Unexpected param for T: %s" % param);
            abort ();
    elif (type == "A"):
        return "$((" + string_of_arg (param) + "))";
    elif (type == "V"):
        assert (len (param) == 4);
        if (param [0] == "Length"):
            (_, _, name, _) = param;
            return "${#" + name + "}";
        else:
            (vt, nul, name, a) = param;

            stri = "${" + name;

            # Depending on who generated the JSON, nul may be
            # a string or a boolean! In Python, non-empty strings
            # to True.
            if (str (nul).lower () == "true"):
                stri += ":";
            elif (str (nul).lower () == "false"):
                pass;
            else:
                os.abort (); # For my own sanity

            stri += string_of_var_type (vt) + string_of_arg (a) + "}";

            return stri;
    elif (type == "Q"):
        return "\"" + string_of_arg (param) + "\"";
    elif (type == "B"):
        return "$(" + to_string (param) + ")";
    else:
        abort ();


# and string_of_arg = function
#   | [] -> ""
#   | c :: a -> string_of_arg_char c ^ string_of_arg a
def string_of_arg (args):
    # print (args);

    text = "".join (map (string_of_arg_char, args));

#    text = "";
#    for arg in args:
#        text = text + string_of_arg_char (arg);

    return (text);


# and string_of_assign (v,a) = v ^ "=" ^ string_of_arg a
def string_of_assign (both):
    (v, a) = both;
    return v + "=" + string_of_arg (a);


# and string_of_case c =
#   let pats = List.map string_of_arg c.cpattern in
#   intercalate "|" pats ^ ") " ^ to_string c.cbody ^ ";;"
def string_of_case (c):
    pats = map (string_of_arg, c ['cpattern']);

    return intercalate ("|", pats) + ") " + to_string (c ['cbody']) + ";;";



# let rec fresh_marker ls s =
#   if List.mem s ls
#   then fresh_marker ls (s ^ (String.sub s (String.length s - 1) 1))
#   else s
#
# OCaml implementation above is O(n^1.5). Algorithm below is linear.
def fresh_marker (heredoc):
    respectsFound = {};

    for line in heredoc.split ('\n'):
        respects = 0;

        if ((len (line) > 2) and (line [0] == 'E') and (line [1] == 'O')):
            for i in range (2, len (line)):
                if (line [i] == 'F'):
                    respects = i - 2;

            respectsFound [respects] = 1;

    i = 0;
    while (True):
        if (not (i in respectsFound)):
            return "EOF" + ("F" * i);

        i = i + 1;


# This version may give an unnecessarily long EOFFFF... (and therefore won't
# match the OCaml output but it is still correct w.r.t. giving a fresh
# marker, and uses less memory than fresh_marker above).
def fresh_marker0 (heredoc):
    maxRespects = 0;

    for line in heredoc.split ('\n'):
        respects = 0;

        if ((len (line) > 2) and (line [0] == 'E') and (line [1] == 'O')):
            for i in range (2, len (line)):
                if (line [i] == 'F'):
                    respects = i - 1;

            maxRespects = max (maxRespects, respects);

    return "EOF" + ("F" * maxRespects);


# and string_of_redir = function
#   | File (To,fd,a)      -> show_unless 1 fd ^ ">" ^ string_of_arg a
#   | File (Clobber,fd,a) -> show_unless 1 fd ^ ">|" ^ string_of_arg a
#   | File (From,fd,a)    -> show_unless 0 fd ^ "<" ^ string_of_arg a
#   | File (FromTo,fd,a)  -> show_unless 0 fd ^ "<>" ^ string_of_arg a
#   | File (Append,fd,a)  -> show_unless 1 fd ^ ">>" ^ string_of_arg a

#   | Dup (ToFD,fd,tgt)   -> show_unless 1 fd ^ ">&" ^ string_of_arg tgt
#   | Dup (FromFD,fd,tgt) -> show_unless 0 fd ^ "<&" ^ string_of_arg tgt
#   | Heredoc (t,fd,a) ->
#      let heredoc = string_of_arg a in
#      let marker = fresh_marker (lines heredoc) "EOF" in
#      show_unless 0 fd ^ "<<" ^
#      (if t = XHere then marker else "'" ^ marker ^ "'") ^ "\n" ^ heredoc ^ marker ^ "\n"
def string_of_redir (redir):
    assert (len (redir) == 2);

    (type, params) = redir;
    if (type == "File"):
        (subtype, fd, a) = params;
        if (subtype == "To"):
            return (show_unless (1, fd) + ">" + string_of_arg (a));
        elif (subtype == "Clobber"):
            return (show_unless (1, fd) + ">|" + string_of_arg (a));
        elif (subtype == "From"):
            return (show_unless (0, fd) + "<" + string_of_arg (a));
        elif (subtype == "FromTo"):
            return (show_unless (0, fd) + "<>" + string_of_arg (a));
        elif (subtype == "Append"):
            return (show_unless (1, fd) + ">>" + string_of_arg (a));
        else:
            abort ();
    elif (type == "Dup"):
        (subtype, fd, tgt) = params;

        if (subtype == "ToFD"):
            return (show_unless (1, fd) + ">&" + string_of_arg (tgt));
        elif (subtype == "FromFD"):
            return (show_unless (0, fd) + "<&" + string_of_arg (tgt));
        else:
            abort ();
    elif (type == "Heredoc"):
        (t, fd, a) = params;

        heredoc = string_of_arg (a);
        marker = fresh_marker (heredoc);

        stri = show_unless (0, fd) + "<<";
        if (t == "XHere"):
            stri += marker;
        else:
            stri += "'" + marker + "'";

        stri += "\n" + heredoc + marker + "\n";

        return (stri);
    else:
        print ("Invalid type: %s" % type);
        abort ();


# and string_of_redirs rs =
#   let ss = List.map string_of_redir rs in
#   (if List.length ss > 0 then " " else "") ^ intercalate " " ss
def string_of_redirs (rs):
#    if (rs == []):
#        return "";
#
#    ss = map (string_of_redir, rs);
#
#    return intercalate (" ", ss);

    str = "";

    for redir in rs:
        str = str + " " + string_of_redir (redir);

    return (str);
