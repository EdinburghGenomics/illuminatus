#!/bin/bash -l
set -uo pipefail
shopt -s nullglob

# cron_o_matic.sh -- Tim Booth, October 2017
#
# We run quite a few cron scripts that really want to run on a continuous
# loop with a pause in between, but cron doesn't provide those semantics.
# Without locking, it's liable to run your script multiple times.
# Also CRON sets a very bare environment by default, and anything that gets
# logged is sent to email, when normally you want stdout going to a log file.
#
# To use this script, add this to the CRON and run as often as you like:
#   env [settings] cron_o_matic.sh <script> [script_args]
#
# Settings may be:
#    CRONJOB_LOCK_NAME - A unique key to lock this job. By default will be
#                        generated from the script name.
#    CRONJOB_LOG_PREFIX - Prefix for log files. Default will be based on the
#                         lock name. 'devnull' to send logs to the bit bucket,
#                         or 'mail' to keep default CRON behaviour.

# 1) Determine LOCK_NAME and LOG_PREFIX
script_basename=$(basename "${1}")
# If the first argument is an executable, assume $1 was the interpreter and
# use that instead,
if [ -x "${2:-}" ] ; then
    script_basename=$(basename "${2}")
fi

script_basename="${script_basename%%.*}"

if [ -z "$script_basename" ]; then
    # Why does your script begin with a .?
    script_basename=$(echo "$1" | md5sum | awk '{print $1}')
fi

if [ -n "${CRONJOB_LOCK_NAME:-}" ] ; then
    _FLOCK_FILE="/tmp/flock_${CRONJOB_LOCK_NAME}"
else
    _FLOCK_FILE="/tmp/flock_${script_basename}"
fi

# If _LOG_FILE was set already assume this script set it before calling itself.
if [ -z "${_LOG_FILE:-}" ] ; then
    if [ -n "${CRONJOB_LOG_PREFIX:-}" ] ; then
        LOG_PREFIX="${CRONJOB_LOG_PREFIX}"
    else
        #See if we can write to /var/log
        if [ -d "/var/log/${script_basename}" ] && [ -w "/var/log/${script_basename}" ] ; then
            LOG_PREFIX="/var/log/$script_basename/${script_basename}"
        else
            mkdir -p "$HOME/cron_logs"
            LOG_PREFIX="$HOME/cron_logs/${script_basename}"
        fi
    fi

    if [ "${LOG_PREFIX}" = 'mail' ] ; then
        _LOG_FILE='-'
    elif [ "${LOG_PREFIX}" = 'devnull' ] ; then
        _LOG_FILE="/dev/null"
    else
        _LOG_FILE="${LOG_PREFIX}.`date +%Y%m%d`.log"
    fi
fi

function log(){
    if [ "$_LOG_FILE" != '-' ] ; then
        echo "=== [`date +'%Y%m%d %H:%M'`] " "$@" >> "$_LOG_FILE"
    else
        echo "=== [`date +'%Y%m%d %H:%M'`] " "$@"
    fi
}

# Do the locking with a write-lock on the _FLOCK_FILE
# I do it like this so I'll get a final hook before launching the script.
if [ "${_FLOCK_ON:-0}" = 0 ] ; then

    # log "Locking on $_FLOCK_FILE, PID=$$"
    (   flock -n 9 || exit 33
        export _FLOCK_ON=9
        source "$0" "$@"
    ) 9>"$_FLOCK_FILE" ; rc="$?"
    if [ "$rc" != 0 ] ; then
        if [ "$rc" = 33 ] ; then
            # This is OK - just means the old process is running
            log "Failed to gain lock on ${_FLOCK_FILE}, `whoami`@`hostname`, PID=$$."
        else
            # This shouldn't happen - errors in the wrapped script are handled below
            log "Script exited with error $rc"
            exit "$rc"
        fi
    fi
    #Spawned copy ran, or else the lock was on - nothing more to do.
    #echo "Exiting unlocked script, PID=$$"
    exit 0
fi

# This cleanly logs Ctrl+C from the terminal plus signals sent to the
# whole process group ( kill TERM -12345 )
for s in TERM INT HUP ; do
   eval trap \""{ log 'Received SIG$s, PID=$$' ; }"\" $s
done

# Now we're the locked copy.
log "Gained lock on ${_FLOCK_FILE}, `whoami`@`hostname`, PID=$$."
log "Running: $*"

# All standard output to the log, if set
if [ "${_LOG_FILE}" != '-' ] ; then
    "$@" >>"${_LOG_FILE}"
    res=$?
else
    "$@"
    res=$?
fi

# Bookend the log entry
if [ "$res" = 0 ] ; then
    log "Completed with status $res, PID=$$."
else
    log "Failed or aborted with status $res, PID=$$."
fi
true
