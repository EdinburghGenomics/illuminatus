#!/usr/bin/env python3

""" Given a run ID, this will poke it into the LIMS so that we can reliably look
    up run flags and such like, and finish the implementation of get_project_from_lims.py.

    At the moment, once a step is tagged we refuse to look and see if there is a newer
    step, but in fact we probably want that feature. In that case the UDF should be
    cleared from the original and tagged onto the new version.

    This script should run, I think, whenever Illuminatus uploads a report. It's
    idempotent, so safe to tag the same run again and again.
"""

import os, sys, re
import configparser

# Seems pointless to use my wrapper lib for this
from pyclarity_lims.lims import Lims

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import logging as L
from pprint import pprint, pformat

QC_PROCESS = "Flow Cell Lane QC EG 1.0 ST"
REPORT_URL_TEMPLATE = "http://web1.genepool.private/runinfo/illuminatus_reports/{}"
# For use in Illuminatus, that should be overridden by the setting we already have in environ.sh:
if os.environ.get("REPORT_LINK"):
    REPORT_URL_TEMPLATE = os.environ.get("REPORT_LINK") + '/{}'

def main(args):

    if args.debug:
        L.basicConfig(format='{name:s} {levelname:s}: {message:s}', level=L.DEBUG, style='{')
        # But silence chatter from pyclarity_lims
        L.getLogger("requests").propagate = False
        L.getLogger("urllib3").propagate = False
    else:
        L.basicConfig(format='{message:s}', level=L.INFO, style='{')

    # Connect to ze lims...
    lims = Lims(**get_config())

    # How to do this?
    # 1 - Firstly look to see if the name is already known. If so, report and exit.
    # 2 - Then split out the flowcell name and look for a container with that name.
    # 3 - If none, exit. If several, pick the latest (highest number)
    # 4 - Find the first analyte and thus the step (see notes)
    # 5 - Load the step and set the values (if not set already or forced)

    # Sanity check, since I accidentally set several run IDs to
    # /lustre/fastqdata/180416_M05898_0001_000000000-D42P7 etc. by foolish use of
    # a shell loop.
    assert re.match(r"^[0-9]{6}_[A-Za-z0-9_-]+", args.runid), \
        "Run ID does not look right - {}".format(args.runid)

    # 1
    existing_proc = lims.get_processes(type=QC_PROCESS, udf={'RunID': args.runid})

    if len(existing_proc):
        L.info("Run {} is already in the LIMS database...".format(args.runid))
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

def get_config(section='genologics', parts=['BASEURI', 'USERNAME', 'PASSWORD']):
    """The genologics.config module is braindead and broken.
       Here's a simplistic reimplementation.
    """
    config = configparser.SafeConfigParser()
    conf_file = config.read(os.environ.get('GENOLOGICSRC',
                            [os.path.expanduser('~/.genologicsrc'),
                             'genologics.conf', 'genologics.cfg', '/etc/genologics.conf'] ))
    L.debug("Read config from {}".format(conf_file))

    return { i.lower(): config[section][i] for i in parts}

def parse_args(*args):

    parser = ArgumentParser( description = "Set run names in the LIMS",
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("runid",
                        help="A run ID, like 180222_K00166_0345_BHT2F5BBXX.")
    parser.add_argument("--container_name",
                        help="Attach the name to a container with the specified name, as" +
                             " opposed to extracting the flowcell name from the runid.")
    parser.add_argument("-c", "--close", "--complete", action="store_true",
                        help="Close/complete the QC step by calling advance().")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Overwrite existing value.")
    parser.add_argument("-n", "--no_act", action="store_true",
                        help="Don't write back to Clarity.")
    parser.add_argument("-v", "--debug", "--verbose", action="store_true",
                        help="Be verbose (debug).")

    return parser.parse_args(*args)


if __name__ == '__main__':
    main(parse_args())
