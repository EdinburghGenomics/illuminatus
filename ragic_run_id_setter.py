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

ragic_form  = "sequencing/2"   # Illumina Run
ragic_query_field = "1000011"  # Flowcell ID
ragic_runid = "Run ID"         # We fill this in.
radic_repurl = "Run QC Report" # and this.

REPORT_URL_TEMPLATE = "http://web1.genepool.private/runinfo/illuminatus_reports/{}"
# For use in Illuminatus, that should be overridden by the setting we already have in environ.sh:
if os.environ.get("REPORT_LINK"):
    REPORT_URL_TEMPLATE = os.environ.get("REPORT_LINK") + '/{}'

def run_to_fcid(runid, container_name):
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

    if container_name:
        # This is here to allow me to force-set run IDs when the container name is wrong
        if fcid != container_name:
            L.warning(f"Forcibly setting run name despite name mismatch -"
                      f" {fcid} from {runid} != {container_name}")

        fcid = container_name

    return fcid

def get_ragic_run(fcid):
    """Get the run from Ragic. Same as found in 

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


    # 1
    fcid = run_to_fcid(args.runid, args.container_name)
    existing_run = get_ragic_run(fcid)

    if len(existing_proc):
        L.info(f"Run {args.runid} is already in the LIMS database...")
        # There should just be one!
        for ep in existing_proc:
            L.info("  " + ep.uri)

            if args.close and not args.no_act:
                try:
                    L.info("  Completing the existing step...")
                    ep.step.get() ; ep.step.advance()
                    L.info("  completed")
                except Exception as e:
                    L.info("  " + str(e))

            if args.debug:
                # It's useful to be able to get the parent process because that's what gets fed
                # into the sample sheet generator.
                for epp_uri in sorted(set(epp.uri for epp in ep.parent_processes())):
                    L.debug("  parent --> " + epp_uri)

        exit(0) # Not an error, but FIXME I should allow the ID to be transferred to a new process.

    # 2
    if args.container_name:
        container_name = args.container_name
    else:
        container_name = re.split('[_-]', args.runid)[-1]

        # Prune off the stage letter.
        mo = re.match(r'[AB](.........)', container_name)
        if mo:
            container_name = mo.group(1)

    existing_containers = lims.get_containers(name=container_name)

    # Sometimes the container in the LIMS is lower case?
    existing_containers.extend(lims.get_containers(name=container_name.lower()))

    # If the container name is not in all upper case then try making it so...
    if container_name != container_name.upper():
        existing_containers.extend(lims.get_containers(name=container_name.upper()))

    # 3
    if len(existing_containers) == 0:
        L.warning("No container found with name {}.".format(container_name))
        exit(1)

    existing_container = sorted(existing_containers, key=lambda c: c.uri)[-1]
    if len(existing_containers) > 1:
        L.warning("Multiple containers found with name {}. The latest ({}) will be used.".format(
                                                       container_name, existing_container.id ))

    L.info("Finding QC step for container {}.".format(existing_container.uri))

    # 4 - HiSeq lane 1 is 1:1 while MiSeq lane is 'A:1' for some reson. We should see on eor the other.
    analyte1, = [ existing_container.placements.get(loc)
                  for loc in ['1:1', 'A:1']
                  if loc in existing_container.placements ]
    L.debug("Examining analyte {}".format(analyte1.uri))

    # https://clarity.genomics.ed.ac.uk/api/v2/processes?type=Flow%20Cell%20Lane%20QC%20EG%201.0%20ST&inputartifactlimsid=2-126766
    # I need to handle the error if there is not one process - older runs lack the step, for example.
    # In the development LIMS we also seem to have multiple QC processes per flowcell. As before I think we need to go for
    # the latest one.
    # Also I've seen a case where a stage was queued and removed (ie. not completed). This shows up on the artifact page but
    # not in the list when I run the get_processes search below.
    try:
        qc_proc = sorted( lims.get_processes(type=QC_PROCESS, inputartifactlimsid=analyte1.id),
                          key = lambda p: p.id )[-1]
    except IndexError:
        L.error("Could not find a QC step for this container.")
        exit(1)

    # 5 - it seems Clarity likes to set UDFs on a step not a process(?)
    qc_step = qc_proc.step.details

    L.info("Setting UDFs on {}".format(qc_step.uri))
    if qc_step.udf.get('RunID'):
        if args.force:
            L.info("Forcing new RunID for step {} in place of '{}' as you requested.".format(qc_step.id, qc_step.udf.get('RunID')))
        else:
            L.info("RunID for step {} is already set to '{}'.".format(qc_step.id, qc_step.udf.get('RunID')))
            exit(1)

    #So, set it...
    qc_step.udf['RunID'] = args.runid
    qc_step.udf['Run Report'] = REPORT_URL_TEMPLATE.format(args.runid)

    L.debug(pformat(qc_step.udf))
    if args.no_act:
        L.info("Nothing will be saved as no_act was set.")
    else:
        qc_step.put()

        if args.close:
            try:
                L.info("Completing the step...")
                qc_proc.step.get(force=True) ; qc_proc.step.advance()
                L.info("completed")
            except Exception as e:
                L.info(str(e))

    L.info("DONE")

def parse_args(*args):

    parser = ArgumentParser( description = "Set run names in the LIMS",
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("runid",
                        help="A run ID, like 180222_K00166_0345_BHT2F5BBXX.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Overwrite existing value.")
    parser.add_argument("-n", "--no_act", action="store_true",
                        help="Don't write back to Ragic.")
    parser.add_argument("-v", "--debug", "--verbose", action="store_true",
                        help="Be verbose (debug).")

    return parser.parse_args(*args)


if __name__ == '__main__':
    main(parse_args())
