#!/usr/bin/env python3
import sys
from subprocess import run, PIPE
from collections import defaultdict as dd

# I currently use RUN_NAME_REGEX to control what runs I want to look at.
# But how do I look back at a window of time?
#  Example uses for this script:
#
# $ env `makeregex.py '1 month ago'` qc_states_report.py
# $ env `makeregex.py '5 weeks ago' A` qc_states_report.py

# Here's the default...
# RUN_NAME_REGEX="${RUN_NAME_REGEX:-.*_.*_.*_[^.]*}"

# So, how do I get from a time specifier to a regex? Well firstly I can use 'date'
# to convert the time spec to a date in YYMMDD format, then list all the dates from then
# to now, and finally compress the regex (with some cunning list operations - hence why
# I need this code to be in Python). Also tack on the machine spec if I want to specify
# just one machine (or type).


def resolve_time_spec(date_str):
    """This is easiest done using the system 'date' command, which knows
       about various ways of expressing relative dates like "June 4 last year".
    """
    cp = run( ["date", "-d", date_str, "+%y%m%d"], universal_newlines=True, stdout=PIPE, check=True )
    return cp.stdout.strip()

def get_dates_list(date_ymd, maxdays=(10*366)):
    """Gets all the valid dates between now and the specified date inclusive.
       Stop if we seem to be going back more than 10 years (which avoids the reverse
       millenium bug).
    """
    #today_ymd = resolve_time_spec('today')
    date_list = []
    days_back = 0

    while True:
        assert days_back < maxdays, "We went back too far - more than %d days." % maxdays

        # Horribly inefficient way of doing things...
        date_list.append(resolve_time_spec('%d days ago' % days_back))

        if date_list[-1] == date_ymd:
            break

        days_back += 1

    return date_list

def list_to_regex(alist):
    """Convert the date list to a regex. Firstly, just concatenate all the days
       together. Then try something a little more economical.

       Note - this code is horrible. But I had as much fun writing it as you will
       have pain reading it, so that's fine.
    """
    # Aggregate final digits.
    d1 = dd(str)
    for d in sorted(alist):
        d1[d[0:5]] += d[5]

    # Find the earliest year...
    min_year = min(k[0:2] for k in d1)

    # And the earliest month (which may or may not be this year)...
    min_month = min(k[0:4] for k in d1)

    # Simplify (knowing these must be valid dates in a continuous range)
    s1 = set()
    s2 = set()
    for k, v in d1.items():
        if k[0:2] != min_year:
            s2.add(k[0:2] + '.*')
        elif k[0:4] != min_month:
            s1.add(k[0:4] + '..')
        elif (k[4] == '3' and v == '01') or (k[4] == '0' and v == '123456789')  or (v == '0123456789'):
            s2.add(k[0:5] + '.')
        elif len(v) == 1:
            s2.add(k[0:5] + v )
        else:
            s2.add(k[0:5] + '[' + v + ']')

    # OK, that's not too bad. Now we can further simplify anything ending in a .. (which is
    # now in s1) to combine whole months.
    d2 = dd(str)
    for d in sorted(s1):
        d2[d[0:3]] += d[3]

    for k, v in d2.items():
        s2.add(k[0:3] + '[' + v + ']..')

    return "(" + "|".join(sorted(s2)) + ")"

def main(args):
    date_str = args[0] if args else '1 week ago'
    machine_name = args[1] if args[1:] else '.*'

    all_dates = get_dates_list(resolve_time_spec(date_str))

    if len(machine_name) == 1:
        machine_name = machine_name + '.*'

    print("RUN_NAME_REGEX=%s_%s_.*_[^.]*" % (list_to_regex(all_dates), machine_name))

main(sys.argv[1:])
