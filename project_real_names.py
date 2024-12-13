#!/usr/bin/env python3
import os, sys, re
import json
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging as L

from illuminatus.RTQuery import get_project_names

def main(args):
    L.basicConfig(level = L.WARNING)

    if args.json:
        json_data = load_json(args.json)
    else:
        json_data = dict()

    # See what projects are in args.proj_numbers that we still need info for
    projects_already_known = set()
    projects_to_fetch = set()
    for pn in args.proj_numbers:
        if (not args.fetchall) and (pn in json_data):
            if json_data[pn].get('name') and not json_data[pn].get('error'):
                L.info(f"Project {pn} already known")
                projects_already_known.add(pn)
    projects_to_fetch = set([ pn for pn in args.proj_numbers
                              if pn not in projects_already_known ])

    # Load what we need to load
    pnl = args.project_name_list or os.environ.get('PROJECT_NAME_LIST', '')
    real_names = project_real_name(projects_to_fetch, pnl)

    # Now update json_data. This involves adding the missing projects and also
    # updating the URLs for everything, just in case the URL template changed.
    save_needed = bool(projects_to_fetch)
    for pn in projects_to_fetch:
        json_data[pn] = real_names[pn]
    for pn in json_data:
        if json_data[pn].get('error'):
            proj_url = f"error: {json_data[pn]['error']}"
        else:
            proj_url = pp_url.format(json_data[pn]['name'])

        if proj_url != son_data[pn].get('url'):
            save_needed = True
            son_data[pn]['url'] = proj_url

    if save_needed and args.update:
        L.info(f"Updating the info in {args.json}")
        try:
            os.path.unlink(args.json)
        except FileNotFoundError:
            pass
        with open(args.json, "x") as fh:
            json.encode something something

def load_json(json_file):
    """This is a bit overblown but there we go.
    """
    try:
        with open(json_file) as fh:
            json_data = json.load(fh)
            json_data.values() # make sure we do have a dict
            return json_data
    except FileNotFoundError:
        # This is fine.
        L.info("File {args.json} does not (yet) exist")
    except json.decoder.JSONDecodeError as e:
        # This is also ok, but a bit funky
        L.warning(f"Failed to load the JSON from {args.json}")
        L.warning(str(e))
    except AttributeError:
        # Ditto
        L.warning(f"{args.json} did not contain a dict")

# In case of problems, return empty dict
return dict()


# A rather contorted way to get project names. We may be able to bypass
# this by injecting them straight into the sample sheet!
def project_real_name(proj_id_list, name_list=''):
    """Resolves a list of project IDs to a name and URL
    """
    res = dict()
    if name_list:
        name_list_split = name_list.split(',')
        # Resolve without going to the LIMS. Note that if you want to disable
        # LIMS look-up without supplying an actuall list of names you can just
        # say "--project_names dummy" or some such thing.
        for p in proj_id_list:
            name_match = [ n for n in name_list_split if n.startswith(p) ]
            if len(name_match) == 1:
                res[p] = dict( name = name_match[0],
                               url  = PROJECT_PAGE_URL.format(name_match[0]) )
            elif p == "ControlLane":
                res[p] = dict( name = p )
            else:
                res[p] = dict( name = p + "_UNKNOWN" )
    else:
        # Go to RT. The current query mode hits the database as configured
        # by ~/.rt_settings and looks for tickets in the eg-projects queue.
        try:

            for p, n in zip(proj_id_list, get_project_names(*proj_id_list)):
                if n:
                    res[p] = dict( name = n,
                                   url = PROJECT_PAGE_URL.format(n) )
                elif p == "ControlLane":
                    res[p] = dict( name = p )
                else:
                    res[p] = dict( name = p + "_UNKNOWN" )
        except Exception as e:
            for p in proj_id_list:
                if p not in res:
                    res[p] = dict( name = p + "_LOOKUP_ERROR",
                                   url = "error://" + repr(e) )

    return res

def parse_args(*args):
    description = """This script is part of the Illuminatus pipeline, but also
                     of more general use.

                     It looks up the real names of projects. Originally these came from
                     the WIKI, then Clarity LIMS, then RT, and soon Ragic. But whatever
                     the source this script should be a drop-in replacement.
                  """

    a = ArgumentParser( description=description,
                        formatter_class = ArgumentDefaultsHelpFormatter )
    a.add_argument("--project_name_list",
                   help="Supply a comma-separated list of project names." +
                        " If you do this, the remote data source will not be queried." +
                        " You can equivalently setenv PROJECT_NAME_LIST." )
    a.add_argument("--json",
                   help="File to store to the retrieved project names.")
    a.add_argument("--update", action="store_true",
                   help="Save now info back to the JSON file")
    a.add_argument("--fetchall", action="store_true",
                   help="Fetch info even if projects are already listed in the JSON file")
    a.add_argument("proj_numbers",
                   help="Projects to get the names for")

    pa = a.parse_args(*args)

    if pa.update and not pa.json:
        exit("If using the --update option, you need to also give a --json file")

    return pa

if __name__ == "__main__":
    main(parse_args())
