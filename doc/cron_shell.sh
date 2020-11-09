#!/bin/bash
set -eu

# This is a hack to allow running cron jobs as the pipeline user despite PAM settings
# demanding that the user have a non-expired password.
# The requirement to set umask after sudo makes it extra hacky - if only the 'env'
# command or the 'sg' command could set the umask we could do it in one pass :-/

current_user=$(id -u)
desired_user=$(stat -c %u "$0")

if [ "$current_user" = "$desired_user" ] ; then

    # We're on the second pass, or were already running as the right user.
    # Change to home dir, set umask and exec Bash
    cd
    umask 0002
    exec "$SHELL" "$@"

else
    if [ "$current_user" != 0 ] ; then
      echo "Only root may use this script to run Bash as $(id -nu $desired_user)"
      exit 1
    fi

    # We're on the first pass. Run sudo.
    exec sudo -H -u "#$desired_user" "$0" "$@"
fi
