#!/bin/env python3

""" Report status of all runs. Dashboard stylee.
    You can report on the live runs from the devel code:
    env RUN_NAME_REGEX='171[012].._.*_.*' ENVIRON_SH=./environ.sh.sample qc_states_report.py
"""

# This was a shell script. Re-written in Python as it was getting silly.
import os, sys, re
from collections import defaultdict
from subprocess import run, PIPE
import pystache
import yaml, yamlloader

# Allow importing of modules from up the way.
PROG_BASE=os.path.dirname(__file__)+'/../..'
sys.path.insert(0,PROG_BASE)

# My souped-up glob
def glob():
    """Regular glob() is useful but it can be improved like so.
    """
    from glob import glob
    return lambda p: sorted( (f.rstrip('/') for f in glob(os.path.expanduser(p))) )
glob = glob()

# Direct import form a runnable program. This should really be made a library.
from RunStatus import RunStatus

# Default environment
environ = dict( ENVIRON_SH = os.environ.get("ENVIRON_SH", "./environ.sh"),
                RUN_NAME_REGEX = ".*_.*_.*_[^.]*" )

# I need to load environ.sh into my environment, which is a little tricky if
# I want to keep allowing general shell syntax in these files (which I do).
def load_environ():
    exports="SEQDATA_LOCATION RUN_NAME_REGEX DEBUG FASTQ_LOCATION"

    #PATH="$(readlink -f "$(dirname $BASH_SOURCE)"/../..):$PATH"
    if os.path.exists(environ['ENVIRON_SH']):
        cpi = run(r'''cd "{}" && source ./"{}" && export {} && printenv'''.format(
                         os.path.dirname(environ['ENVIRON_SH']),
                                          os.path.basename(environ['ENVIRON_SH']),
                                                         exports ),
                shell = True,
                stdout = PIPE,
                universal_newlines = True)

        environ.update([ l.split('=',1) for l in cpi.stdout.split('\n') if '=' in l ])

def debug(*args):
    """ Poor mans logger
    """
    if environ.get('DEBUG') and environ.get('DEBUG') != '0':
        print(*args)
        return True
    return False

# Behaviour should match what's in driver.sh
def main(args):

    load_environ()

    print("Looking for run directories matching regex {}/{}".format(
                environ['SEQDATA_LOCATION'], environ['RUN_NAME_REGEX'] ))

    rnr = environ['RUN_NAME_REGEX']
    if not rnr.endswith('$'):
        rnr += '$'
    rnr = re.compile(rnr)

    res = defaultdict(lambda: dict(
            rcount = 0,
            runs = [],
            instruments = defaultdict(int)
        ))
    pversions = dict()

    # Scan all of the directories in quick mode, but only if the match the regex
    for arun in glob(environ['SEQDATA_LOCATION'] + '/*/'):

        runid = os.path.basename(arun)

        if not re.match(rnr, runid):
            debug("Ignoring {} - regex mismatch".format(runid))
            continue

        # We just need to know about the instrument and status, which
        # can be done quickly.
        # You can ask the same by running RunStatus.py -q ...
        rs = RunStatus(arun, 'q')

        # Note I'm overwriting runid - this will prune any .extension
        runid = rs.runinfo_xml.run_info['RunId']
        rinstrument = rs.runinfo_xml.run_info['Instrument']
        rstatus = rs.get_status()

        # Sanity check and print a warning if there is no symlimk and the dir names mismatch
        if (not os.path.exists("{}/pipeline/output".format(arun)) and
            not os.path.exists("{}/{}".format(environ['FASTQ_LOCATION'], runid)) and
            rstatus not in ['new', 'aborted']):
            print("{} has a pipeline dir but no fastq directory!".format(runid))

        # Collect the runs by status and instrument counts
        res[rstatus]['rcount'] += 1
        res[rstatus]['runs'].append(runid)
        res[rstatus]['instruments'][rinstrument] += 1

        # If complete, see what version it was done with.
        # Normally, skip this. It's too slow.
        if debug():
            if rstatus == "complete":
                for f in glob(arun + "/pipeline/output/QC/run_info.*.yml"):
                    with open(f) as fh:
                        fdata = yaml.safe_load(fh)
                        for sect in fdata.values():
                            if 'Pipeline Version' in sect:
                                pversions[runid] = fdata['Pipeline Version']
            debug("Run {} completed with pipeline version {}".format(runid, pversions[runid]))

    #End of loop through directories. Now rearrange instruments from a defaultdict to a list and print.
    for resv in res.values():
        resv['instruments'] = [ dict(name=k, count=v) for k, v in sorted(resv['instruments'].items()) ]

    print("### Run report as YAML:")
    print(yaml.dump(dict_strip(res), Dumper=yamlloader.ordereddict.CSafeDumper))

    # Now lets render that puppy as PDF (needs pystache which I'll add to the project)...
    # Since the PDF is disposable I'll just clobber it for now.
    ##msrender -d "$OFH" -- "$(dirname $BASH_SOURCE)"/qc_states.gv.tmpl | dot -Tpdf -o "$(dirname $BASH_SOURCE)"/qc_states_scanned.pdf
    render_pdf(res)

def render_pdf(res):

    template = os.path.join(PROG_BASE, 'templates', 'qc_states.gv.tmpl')
    pdf = os.path.join(PROG_BASE, 'reports', 'qc_states_scanned.pdf')

    # Now load and render the template
    with open(template) as tfh:
        rendered = pystache.render(tfh.read(), res)

    os.makedirs(os.path.dirname(pdf), exist_ok=True)
    run(r'''dot -Tpdf -o "{}"'''.format(pdf), shell=True, check=True, input=rendered, universal_newlines=True)

    # TODO - let us configure where reports go.
    print("See PDF in {}".format(pdf))

def dict_strip(x):
    """As I've switched from YAMLOrdered to yamlloader I can no longer dump
       default dicts. Meh.
       This recursively converts all defaultdicts to dicts.
       No loop detection so be careful!
    """
    if type(x) in [dict, defaultdict]:
        return { k: dict_strip(v) for k, v in x.items() }
    elif type(x) in [list, tuple]:
        return [ dict_strip(v) for v in x ]
    else:
        return x


if __name__ == '__main__':
    main(sys.argv[1:])
