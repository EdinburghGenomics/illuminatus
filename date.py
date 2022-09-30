#!/usr/bin/env python3

import sys
from datetime import datetime
from illuminatus.Formatters import fmt_time

"""Simply print the current date/time (or a specific timestamp) as per fmt_time
"""

if sys.argv[1:]:
    print( fmt_time(int(sys.argv[1])) )
else:
    print( fmt_time() )
