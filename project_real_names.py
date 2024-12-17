#!/usr/bin/env python3
import os, sys, re
import json
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from urllib.parse import quote as url_quote
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
    real_names = project_real_names(projects_to_fetch, pnl)

    # Project links can similarly be set by an environment var
    project_page_url = (args.project_page_url or
                         os.environ.get('PROJECT_PAGE_URL', "http://foo.example.com/") )
    try:
        if project_page_url.format('test') == project_page_url:
            project_page_url += '{}'
    except Exception:
        L.error(f"The environment variable PROJECT_PAGE_URL={PROJECT_PAGE_URL}"
                 " is not a valid format string.")
        raise

    # Now update json_data. This involves adding the missing projects and also
    # updating the URLs for everything, just in case the URL template changed.
    save_needed = bool(projects_to_fetch)
    for pn in projects_to_fetch:
        # Add in new project and set the URL correctly
        json_data[pn] = real_names[pn]
        json_data[pn]['url'] = gen_url(json_data[pn], project_page_url)
    for pn in json_data:
        # Re-make the URL for the existing project names to see if it
        # needs changing
        proj_url = gen_url(json_data[pn], project_page_url)

        if proj_url != json_data[pn].get('url'):
            save_needed = True
            json_data[pn]['url'] = proj_url

    if save_needed and args.update:
        L.info(f"Updating the info in {args.json}")
        try:
            os.unlink(args.json)
        except FileNotFoundError:
            pass
        with open(args.json, "x") as fh:
            json.dump(json_data, fh, sort_keys=True, indent=4)
            fh.write("\n")
    elif not args.update:
        # Just print the result
        print( json.dumps(json_data, sort_keys=True, indent=4) )

def is_special_name(project_name):
    """Names that we treat specially
    """
    return project_name in ['ControlLane']

def gen_url(proj_info, url_template):
    """proj_info should be a dict with and 'error' or 'name' key
       url_template should be a string with a {} placeholder for the project name
    """
    if proj_info.get('error'):
        return f"error: {proj_info['error']}"
    elif is_special_name(proj_info['name']):
        return None
    else:
        return url_template.format(url_quote(proj_info['name']))


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
def project_real_names(proj_id_list, name_list=''):
    """Resolves a list of project IDs to a name, or gives a
       dummy name and an error.
    """
    # Tackle the reserved names fist. We don't look these up.
    res = { p: dict(name=p) for p in proj_id_list if is_special_name(p) }
    proj_id_list = [ p for p in proj_id_list if not is_special_name(p) ]

    if name_list:
        name_list_split = name_list.split(',')
        # Resolve without going to the LIMS. Note that if you want to disable
        # LIMS look-up without supplying an actual list of names you can just
        # say "--project_names dummy" or some such thing.
        for p in proj_id_list:
            name_match = [ n for n in name_list_split if n.startswith(p) ]
            if len(name_match) == 1:
                res[p] = dict( name = name_match[0] )
            else:
                res[p] = dict( name = p + "_UNKNOWN",
                               error = "not listed in PROJECT_NAME_LIST" )
    else:
        # Go to RT. The current query mode hits the database as configured
        # by ~/.rt_settings and looks for tickets in the eg-projects queue.
        try:
            for p, n in zip(proj_id_list, get_project_names(*proj_id_list)):
                if n:
                    res[p] = dict( name = n )
                else:
                    res[p] = dict( name = p + "_UNKNOWN",
                                   error = "not listed in RT" )
        except Exception as e:
            # Deals with general connection failures etc.
            for p in proj_id_list:
                if p not in res:
                    res[p] = dict( name = p + "_LOOKUP_ERROR",
                                   error = repr(e) )

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
                   help="Supply a comma-separated list of project names."
                        " If you do this, the remote data source will not be queried."
                        " You can equivalently setenv PROJECT_NAME_LIST." )
    a.add_argument("--project_page_url",
                   help="Template for making URL links to projects. May contain a single"
                        " {} placeholder or else the project name will be appended")
    a.add_argument("--json",
                   help="File to read for previously retrieved project names.")
    a.add_argument("--update", action="store_true",
                   help="Save new info back to the JSON file")
    a.add_argument("--fetchall", action="store_true",
                   help="Fetch info even if projects are already listed in the JSON file")
    a.add_argument("proj_numbers", nargs='+',
                   help="Projects to get the names for")

    pa = a.parse_args(*args)

    if pa.update and not pa.json:
        exit("If using the --update option, you need to also give a --json file")

    return pa

if __name__ == "__main__":
    main(parse_args())
