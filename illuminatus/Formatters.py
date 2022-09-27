#!/usr/bin/env python3

# Some data formatters that I seem to need from time to time...

def rat(n, d, nan=float('nan'), mul=1.0):
    """ Calculate a ratio while avoiding division by zero errors.
        Strictly speaking we should have nan=float('nan') but for practical
        purposes we'll maybe want to report None (or 0.0?).
    """
    try:
        return ( float(n) * mul ) / float(d)
    except (ZeroDivisionError, TypeError):
        return nan

def pct(n, d, mul=100.0, **kwargs):
    """ Percentage by the same logic.
        You can override mul and nan if you like.
    """
    return rat(n, d, mul=mul, **kwargs)

def fmt_time(d):
    """ Format a datetime for the report. We used to just use .ctime() but Matt
        asked for something that Excel would recognise.
    """
    return d.strftime("%a %d-%h-%Y %H:%M:%S")
