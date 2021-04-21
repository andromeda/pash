#!/bin/bash

## File directory
RUNTIME_DIR=$(dirname "${BASH_SOURCE[0]}")

still_alive()
{
    jobs -p | tr '\n' ' '
}

log()
{
    pash_redir_output echo "$$: (QAbort) " "$@"
}

# Taken from: https://stackoverflow.com/a/20473191
# list_include_item "10 11 12" "2"
function list_include_item {
  local list="$1"
  local item="$2"
  if [[ $list =~ (^|[[:space:]])"$item"($|[[:space:]]) ]] ; then
    # yes, list include item
    result=0
  else
    result=1
  fi
  return $result
}

## This spawns a buffer command to buffer inputs and outputs
##
## It writes the pid to stdout
spawn_eager()
{
    local name=$1
    local input=$2
    local output=$3
    local eager_file="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    ## Note: Using eager actually leads to some deadlock issues. It must have to do with eagers behavior when
    ##       its input or output closes.
    # "$RUNTIME_DIR/../runtime/eager" "$input" "$output" "$eager_file" </dev/null 1>/dev/null 2>/dev/null &
    "$RUNTIME_DIR/../runtime/dgsh_tee.sh" "$input" "$output" -I -f </dev/null 1>/dev/null 2>/dev/null &
    local eager_pid=$!
    log "Spawned $name eager: $eager_pid with:"
    log "  -- IN: $input"
    log "  -- OUT: $output"
    log "  -- INTERM: $eager_file"
    echo "$eager_pid"
}

## Kills the process group that belongs to the given pgid
kill_pg()
{
    local pg_lead_pid=$1
    /bin/kill -15 "-${pg_lead_pid}" 2> /dev/null
}

## TODO: Make sure that this waits for all processes in the process group to finish executing.
wait_pg()
{
    local pg_lead_pid=$1
    wait "$pg_lead_pid" 2> /dev/null    
}

kill_wait_pg()
{
    kill_pg "$1"
    wait_pg "$1"
}

## Solution Schematic:
##
##  (A)      (B)      (C)       (D)        (E)
## stdin --- tee --- eager --- seq.sh --- eager --- OUT_SEQ
##            \      (F)
##             \--- eager --- PAR_IN
##
## (1) If compiler fails, or sequential is done executing:
##     - cat OUT_SEQ > stdout
##
## (2) If compiler succeeds:
##     - USR1 to reroute so that it redirects to /dev/null
##     - PAR_IN redirect to par stdin.
##
## Simplifying assumptions:
## - Not worrying about stderr
## - Not worrying about other inputs at the moment (assuming they are files if compiler succeeds)
## - Not worrying about other outputs 
##   + assuming that the parallel implementation will overwrite them
##   + Assuming that the DFG outputs are not appended
##
## TODO: A first TODO would be to check them in the compilation process
##
## TODO: An alternative TODO would be to let preprocessing give us information about them, allowing us to 
##       have a finer tuned execution plan depending on this information. For example, if we see that script
##       has append to some file we can be carefull and buffer its output using eager.

## NOTE: The intuition about why quick-abort works is that if the compilation succeeds, then the
##       script is a DFG, meaning that we know exactly how it affects its environment after completing.
##       Therefore, we can go back and stop the already running script without risking unsafe behavior.

## TODO: We also want to avoid executing the compiled script if it doesn't contain any improvement.

## TODO: Maybe the reroute needs to be put around (C) and not (D)

## TODO: Improve the happy path (very fast sequential) execution time 

## TODO: Use reroute around dgsh_tees to make sure that they do not use storage unnecessarily 
##       (if their later command is done).

if [ "$pash_execute_flag" -eq 1 ]; then
    # set -x
    ## (A) Redirect stdin to `tee`
    pash_tee_stdin="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    mkfifo "$pash_tee_stdin"
    ## The redirections below are necessary to ensure that the background `cat` reads from stdin.
    { setsid cat > "$pash_tee_stdin" <&3 3<&- & } 3<&0
    pash_input_cat_pid=$!
    log "Spawned input cat with pid: $pash_input_cat_pid"

    ## (B) A `tee` that duplicates input to both the sequential and parallel
    pash_tee_stdout1="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    pash_tee_stdout2="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    mkfifo "$pash_tee_stdout1" "$pash_tee_stdout2"
    tee "$pash_tee_stdout1" > "$pash_tee_stdout2" < "$pash_tee_stdin" &

    ## (C) The sequential input eager
    pash_seq_eager_output="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    mkfifo "$pash_seq_eager_output"
    seq_input_eager_pid=$(spawn_eager "sequential input" "$pash_tee_stdout1" "$pash_seq_eager_output")

    ## (D) Sequential command
    pash_seq_output="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    mkfifo "$pash_seq_output"
    setsid "$RUNTIME_DIR/pash_wrap_vars.sh" \
        $pash_runtime_shell_variables_file \
        $pash_output_variables_file \
        ${pash_output_set_file} \
        ${pash_sequential_script_file} \
        > "$pash_seq_output" < "$pash_seq_eager_output" &
    pash_seq_pid=$!
    log "Sequential pid: $pash_seq_pid"

    ## (E) The sequential output eager
    pash_seq_eager2_output="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    mkfifo "$pash_seq_eager2_output"
    seq_output_eager_pid=$(spawn_eager "sequential output" "$pash_seq_output" "$pash_seq_eager2_output")

    ## (F) Second eager
    pash_par_eager_output="$($RUNTIME_DIR/pash_ptempfile_name.sh)"
    mkfifo "$pash_par_eager_output"
    par_eager_pid=$(spawn_eager "parallel input" "$pash_tee_stdout2" "$pash_par_eager_output")

    ## Run the compiler
    setsid python3 -S "$RUNTIME_DIR/pash_runtime.py" ${pash_compiled_script_file} --var_file "${pash_runtime_shell_variables_file}" "${@:2}" &
    pash_compiler_pid=$!
    log "Compiler pid: $pash_compiler_pid"

    ## Wait until one of the two (original script, or compiler) die
    alive_pids=$(still_alive)
    log "Still alive: $alive_pids"
    while `list_include_item "$alive_pids" "$pash_seq_pid"` && `list_include_item "$alive_pids" "$pash_compiler_pid"` ; do
        ## Wait for either of the two to complete
        wait -n "$pash_seq_pid" "$pash_compiler_pid"
        completed_pid_status=$?
        log "Process exited with return code: $completed_pid_status"
        alive_pids=$(still_alive)
        log "Still alive: $alive_pids"
    done

    ## If the sequential is still alive we want to see if the compiler succeeded
    if `list_include_item "$alive_pids" "$pash_seq_pid"` ; then
        pash_runtime_return_code=$completed_pid_status
        log "Compilation was done first with return code: $pash_runtime_return_code"

        ## We only want to run the parallel if the compiler succeeded.
        if [ "$pash_runtime_return_code" -eq 0 ]; then

            ## TODO: Is this necessary
            ## Redirect the sequential output to /dev/null
            cat "$pash_seq_eager2_output" > /dev/null &
            seq_cat_pid=$!
            log "seq to /dev/null cat pid: $seq_cat_pid"

            ## Kill the sequential process tree
            log "Killing sequential pid: $pash_seq_pid..."
            kill_pg "$pash_seq_pid"
            kill_status=$?
            wait_pg "$pash_seq_pid"
            seq_exit_status=$?
            log "Sequential pid: $pash_seq_pid was killed successfully returning status $seq_exit_status."
            log "Still alive: $(still_alive)"

            ## If kill failed it means it was already completed, 
            ## and therefore we do not need to run the parallel.
            ##
            ## TOOD: Enable this optimization
            if true || [ "$kill_status" -eq 0 ]; then
                ## (2) Run the parallel
                log "Run parallel:"
                log "  -- Runtime vars: $pash_runtime_shell_variables_file"
                log "  -- Output vars: $pash_output_variables_file"
                log "  -- Output set: ${pash_output_set_file}"
                log "  -- Compiled script: ${pash_compiled_script_file}"
                log "  -- Input: $pash_par_eager_output"

                "$RUNTIME_DIR/pash_wrap_vars.sh" \
                    $pash_runtime_shell_variables_file \
                    $pash_output_variables_file \
                    ${pash_output_set_file} \
                    ${pash_compiled_script_file} \
                    < "$pash_par_eager_output" &
                ## Note: For some reason the above redirection used to create some issues,
                ##       but no more after we started using dgsh-tee

                pash_par_pid=$!
                log "Parallel is running with pid: $pash_par_pid..."
                # strace -p $pash_par_pid 2>> $PASH_REDIR
                wait "$pash_par_pid"
                pash_runtime_final_status=$?
                log "Parallel is done with status: $pash_runtime_final_status"
            else
                ## TODO: Handle that case properly by enabling the optimization above.
                log "ERROR: Shouldn't have reached that"
                exit 1
            fi
        else
            ## If the compiler failed we just wait until the sequential is done.

            ## (1) Redirect the seq output to stdout
            cat "$pash_seq_eager2_output" &
            seq_output_cat_pid=$!
            log "STDOUT cat pid: $seq_output_cat_pid"

            log "Waiting for sequential: $pash_seq_pid"
            wait "$pash_seq_pid"
            pash_runtime_final_status=$?
            log "DONE Sequential: $pash_seq_pid exited with status: $pash_runtime_final_status"

            ## TODO: It is not clear if we also need to wait for the output cat to end.
            log "Waiting for sequential output cat: $seq_output_cat_pid"
            wait "$seq_output_cat_pid"
            log "DONE Waiting for sequential output cat: $seq_output_cat_pid"

        fi
    else
        pash_runtime_final_status=$completed_pid_status
        log "Sequential was done first with return code: $pash_runtime_final_status"

        ## (1) Redirect the seq output to stdout
        cat "$pash_seq_eager2_output" &
        final_cat_pid=$!
        log "STDOUT cat pid: $final_cat_pid"

        ## We need to kill the compiler to not get delayed log output
        ## If this fails (meaning that compilation is done) we do not care
        kill_wait_pg "$pash_compiler_pid"

        wait "$final_cat_pid"
    fi

    ## TODO: Not clear if this is needed or if it doesn indeed kill all the
    ##       processes and cleans up everything properly
    ## Kill the input process
    log "Killing the input cat process: $pash_input_cat_pid"
    kill_wait_pg "$pash_input_cat_pid"
    # kill -9 $pash_input_cat_pid 2> /dev/null
    # wait $pash_input_cat_pid 2> /dev/null
    log "The input cat: $pash_input_cat_pid died!"
    

    ## TODO: This (and the above) should not be needed actually, everything should be already done due to
    ##       sequential and parallel both having exited.
    ## Kill every spawned process
    still_alive_pids="$(still_alive)"
    log "Killing all the still alive: $still_alive_pids"
    kill -15 "$still_alive_pids" 2> /dev/null
    wait $still_alive_pids 2> /dev/null
    log "All the alive pids died: $still_alive_pids"
    
    ## Return the exit code
    (exit "$pash_runtime_final_status")
fi
