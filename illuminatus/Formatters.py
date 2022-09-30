#!/usr/bin/env python3

# Some data formatters that I seem to need from time to time...

from datetime import datetime, timedelta

def rat(n, d, nan=float('nan'), mul=1.0):
    """Calculate a ratio while avoiding division by zero errors.
       Strictly speaking we should have nan=float('nan') but for practical
       purposes we'll maybe want to report None (or 0.0?).
    """
    try:
        return ( float(n) * mul ) / float(d)
    except (ZeroDivisionError, TypeError):
        return nan

def pct(n, d, mul=100.0, **kwargs):
    """Percentage by the same logic.
       You can override mul and nan if you like.
    """
    return rat(n, d, mul=mul, **kwargs)

def fmt_time(ts=None):
    """Format a timestamp for the report. We used to just use .ctime() but Matt
       asked for something that Excel would recognise.

       ts - an integer containing a Unix timestamp
    """
    if ts:
        dt = datetime.fromtimestamp(ts)
    else:
        dt = datetime.now()
    return dt.strftime("%a %d-%h-%Y %H:%M:%S")

def fmt_duration(start_ts, end_ts=None):
    """Given two integers representing Unix timestamps, show the duration as
       'x hours, y minutes'
       If only one time is given, give the duration between then and now.
    """
    if end_ts is None:
        end_ts = datetime.now().timestamp()

    if end_ts < start_ts:
        return "invalid negative duration"

    duration = datetime.fromtimestamp(end_ts) - datetime.fromtimestamp(start_ts)

    hours = duration // timedelta(hours=1)
    minutes = (duration % timedelta(hours=1)) // timedelta(minutes=1)

    return f"{hours} hours {minutes:02d} minutes"
