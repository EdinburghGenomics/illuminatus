#!/bin/bash -l
set -e
set -u

# Eventually, the driver.sh script should be ready to be called directly
# from the CRON, but for now we need to rsync new data across from /ifs/seqdata
# because that's invisible to the cluster nodes.
# This script will do that for us.

# Normally, the driver will run from the CRON every 5 minutes and locking at the
# project level will be used to prevent two instances interfering. Also, seeing an
# incomplete project is not a problem because the files appear in the expected order.
# But with RSync we can't guarantee that, so we must lock.


# Settings in driver.sh to override.
export SEQDATA_LOCATION=/lustre/seqdata
export FASTQ_LOCATION=/lustre/fastqdata
export LOG_DIR=~pipeline/illuminatus/logs

# With RSYNC, we don't want two syncs operating at once and also we don't want to
# let the driver run while RSYNC is running because it might copy the touch file
# before all the data is done.
#
# For RapidQC I used 'ps' to see if the script was already running, but I think a
# flock-based solution is actually much neater.
# Should really flock on something in /var/run/lock but that gets killed on reboot
# and only root can re-make the file. So use /tmp instead.
#

# 1) Engage shared lock
FLOCK_FILE="/tmp/flock_$(readlink -f "$0" | md5sum | awk '{print $1}')"
if [ "${FLOCK_ON:-0}" = 0 ] ; then
    # echo "Locking on $FLOCK_FILE, PID=$$"
    (   flock -s -n 9 || exit 33
        export FLOCK_ON=9
        source "$0" "$@"
    ) 9>"$FLOCK_FILE" ; rc="$?"
    if [ "$rc" != 0 ] ; then
        if [ "$rc" = 33 ] ; then
            echo "Failed to gain shared lock, PID=$$"
        else
            echo "Script exited with error $rc"
        fi
        exit "$rc"
    fi
    #Spawned copy ran, nothing more to do.
    #echo "Exiting unlocked script, PID=$$"
    exit 0
fi
#echo "Locked on $FLOCK_FILE, PID=$$"

# 2) Attempt to upgrade to exclusive lock, and run RSYNC if successful
if flock -x -n $FLOCK_ON ; then
    #echo "Entering exclusive section, PID=$$"

    # 2a) Ensure that the directory is there for the rsync log
    mkdir -p "$LOG_DIR"
    echo "=== Running $0 at `date` ===" >> "$LOG_DIR"/rsync.log

    # Run rsync. But just running rsync on everything will take way too long, so we need a smarter strategy.

    # 2b) Only look at the last 20 days fo runs
    newish_runs=($(find /ifs/seqdata/17*_*_*_* -maxdepth 0 -mindepth 0 -type d -mtime '-20'))

    echo "Starting rsync on ${newish_runs[@]}" >> "$LOG_DIR"/rsync.log

    # 2c) Rsync just the bare bones of these
    rsync -av --exclude='Data/*' --exclude='Images/*' --exclude='Thumbnail_Images/*' --exclude='Logs/*' \
        --exclude=RTAComplete.txt \
        "${newish_runs[@]}" /lustre/seqdata >> "$LOG_DIR"/rsync.log 2>&1

    # 2d) Find any directory on /lustre where the RTAComplete.txt file is missing and do a full RSYNC
    #     if there is a corresponding RTAComplete.txt on /ifs.
    for dest_run in /lustre/seqdata/17*_*_*_* ; do
        if [ ! -e "$dest_run/RTAComplete.txt" ] ; then
            src_run="/ifs/seqdata/$(basename $dest_run)"
            if [ -e "$src_run/RTAComplete.txt" ] ; then
                #Now bring the whole run across. I considered explicitly copying RTAComplete.txt right at the end but
                #it seems like overkill.
                rsync -av "$src_run" /lustre/seqdata >> "$LOG_DIR"/rsync.log 2>&1
            fi
        fi
    done

    #echo "Leaving exclusive section, PID=$$"
    # Return to shared lock
    flock -s $FLOCK_ON
#else
    #echo "Failed to gain exclusive lock, PID=$$"
fi

# 4) Aaaaand finally, we can run driver.sh
$(dirname $(readlink -f "$0"))/driver.sh
