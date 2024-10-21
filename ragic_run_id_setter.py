#!/usr/bin/env python3

""" Given a run ID, this will poke it into Ragic so that we can reliably look
    up run flags and such like, and finish the implementation of get_project_from_ragic.py.

    This script should run, I think, whenever Illuminatus uploads a report. It's
    idempotent, so safe to tag the same run again and again.
"""

import os, sys, re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging as L
from pprint import pprint, pformat

from illuminatus import ragic

# FIXME - check with PyFlakes what I'm actually using
ragic_form  = "sequencing/2"   # Illumina Run
ragic_query_field = "1000011"  # Flowcell ID
ragic_runid = "Run ID"         # We fill this in.
radic_repurl = "Run QC Report" # and this.

REPORT_URL_TEMPLATE = "http://web1.genepool.private/runinfo/illuminatus_reports/{}"
# For use in Illuminatus, that should be overridden by the setting we already have in environ.sh:
if os.environ.get("REPORT_LINK"):
    REPORT_URL_TEMPLATE = os.environ.get("REPORT_LINK") + '/{}'

def run_to_fcid(runid, container_name=None):
    # Sanity check, since I accidentally set several run IDs to
    # /lustre/fastqdata/180416_M05898_0001_000000000-D42P7 etc. by foolish use of
    # a shell loop.
    if not re.match(r"^[0-9]{6}_[A-Za-z0-9_-]+", runid):
        raise TypeError(f"Run ID does not look right - {runid}")

    fcid = re.split('[_-]', runid)[-1]

    # Prune off the stage letter.
    mo = re.match(r'[AB](.........)', fcid)
    if mo:
        fcid = mo.group(1)

    # And always make it upper case. Validation rule in Ragic should ensure the records
    # in there are all upper case.
    fcid = fcid.upper()

    if container_name:
        # This is here to allow me to force-set run IDs when the container name is wrong
        if fcid != container_name:
            L.warning(f"Forcibly setting run name despite name mismatch -"
                      f" {fcid} from {runid} != {container_name}")

        fcid = container_name

    return fcid

def main(args):

    if args.debug:
        L.basicConfig(format='{name:s} {levelname:s}: {message:s}', level=L.DEBUG, style='{')
    else:
        L.basicConfig(format='{message:s}', level=L.INFO, style='{')

    # How to do this?
    # 1 - Split out the flowcell name and look for a Ragic record with that name.
    # 2 - If none, exit with error. If several, pick the latest (highest number)
    # 3 - See if the name is already known. If so, check the match and exit.
    # 4 - Set the values (if not set already or forced)


    # 1+2. Logic for getting the run is the same as used in samplesheet_from_ragic, but
    # we do not care about the samples.
    fcid = run_to_fcid(args.runid, args.container_name)
    rc = ragic.get_rc()
    try:
        existing_run = ragic.get_run(fcid, add_samples=False, rc=rc)
    except ragic.EmptyResultError:
        L.warning(f"No Illumina Run found in Ragic for flowcell {fcid}.")
        exit(1)

    # 3
    if existing_run['Run ID']:
        if args.force:
            L.warning(f"Run ID is already set to {existing_run['Run ID']}"
                      f" but forcing as requested.")

        elif existing_run['Run ID'] == args.runid:
            L.info(f"Run ID is already set to {existing_run['Run ID']}"
                   f" so nothing to be done.")
            exit(0)
        else:
            L.info(f"Run ID is already set to {existing_run['Run ID']}"
                   f" but this does not match {args.runid}.")
            exit(1)

    # 4. In Ragic, to set individual values we just pass a dict of the stuff to
    # be changed.
    id_and_report = { '1000037': 'hello', 'Run ID': args.runid,
                      'Run QC Report': REPORT_URL_TEMPLATE.format(args.runid) }

    L.info(f"Updating Ragic record with ID {existing_run['_ragicId']}")
    L.debug(pformat(id_and_report))
    if args.no_act:
        L.info("Nothing will be saved as no_act was set.")
    else:
        ragic.put_run(existing_run['_ragicId'], id_and_report, rc=rc)

    L.info("DONE")

def parse_args(*args):

    parser = ArgumentParser( description = "Set run names in the LIMS",
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("runid",
                        help="A run ID, like 180222_K00166_0345_BHT2F5BBXX.")
    parser.add_argument("--container_name",
                        help="Attach the name to a container with the specified name, as" +
                             " opposed to extracting the flowcell name from the runid.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Overwrite existing value.")
    parser.add_argument("-n", "--no_act", action="store_true",
                        help="Don't write back to Ragic.")
    parser.add_argument("-v", "--debug", "--verbose", action="store_true",
                        help="Be verbose (debug).")

    return parser.parse_args(*args)


if __name__ == '__main__':
    main(parse_args())
