#!/usr/bin/env python3
import os, sys, re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from urllib.parse import quote as url_quote
import logging as L

from illuminatus.SampleSheetReader import SampleSheetReader
from illuminatus.RTQuery import get_project_names
from illuminatus.yaml import load_yaml, dump_yaml, ParserError

def main(args):
    L.basicConfig(level = L.WARNING)

    if args.yaml:
        yaml_data = try_load_yaml(args.yaml)
    else:
        yaml_data = dict()

    proj_numbers = set(args.proj_numbers)

    if args.sample_sheet:
        # Allow any exceptions to propagate. This means if the sample
        # sheet is invalid no YAML file will be saved.
        ss_csv = SampleSheetReader(args.sample_sheet)

        for line in ss_csv.samplesheet_data:
            proj_numbers.add(line[ss_csv.column_mapping['sample_project']])

    # See what projects are in proj_numbers that we still need info for
    projects_already_known = set()
    for pn in proj_numbers:
        if (not args.fetchall) and (pn in yaml_data):
            if yaml_data[pn].get('name') and not yaml_data[pn].get('error'):
                L.info(f"Project {pn} already known")
                projects_already_known.add(pn)
    projects_to_fetch = proj_numbers.difference(projects_already_known)

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
        L.error(f"The setting for PROJECT_PAGE_URL={project_page_url}"
                 " is not a valid format string.")
        raise

    # Now update yaml_data. This involves adding the missing projects and also
    # updating the URLs for everything, just in case the URL template changed.
    save_needed = bool(projects_to_fetch)
    for pn in projects_to_fetch:
        # Add in new project and set the URL correctly
        yaml_data[pn] = real_names[pn]
        yaml_data[pn]['url'] = gen_url(yaml_data[pn], project_page_url)
    for pn in yaml_data:
        # Re-make the URL for the existing project names to see if it
        # needs changing
        proj_url = gen_url(yaml_data[pn], project_page_url)

        if proj_url != yaml_data[pn].get('url'):
            save_needed = True
            yaml_data[pn]['url'] = proj_url

    if save_needed and args.update:
        L.info(f"Updating the info in {args.yaml}")
        try:
            os.unlink(args.yaml)
        except FileNotFoundError:
            pass
        dump_yaml(yaml_data, filename=args.yaml, mode="x")
    elif not args.update:
        # Just print the result
        dump_yaml(yaml_data, fh=sys.stdout)

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


def try_load_yaml(yaml_file):
    """This is a bit overblown but there we go.
    """
    try:
        yaml_data = load_yaml(yaml_file)
        yaml_data.values() # make sure we do have a dict
        return yaml_data
    except FileNotFoundError:
        # This is fine.
        L.info("File {yaml_file} does not (yet) exist")
    except ParserError as e:
        # This is also ok, but a bit funky
        L.warning(f"Failed to load the JSON from {yaml_file}")
        L.warning(str(e))
    except AttributeError:
        # Ditto
        L.warning(f"{yaml_file} did not contain a dict")

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
    a.add_argument("--yaml",
                   help="File to read for previously retrieved project names.")
    a.add_argument("--update", action="store_true",
                   help="Save new info back to the JSON file")
    a.add_argument("--fetchall", action="store_true",
                   help="Fetch info even if projects are already listed in the JSON file")
    a.add_argument("--sample_sheet",
                   help="Read the SampleSheet.csv to see what projects to look up")
    a.add_argument("proj_numbers", nargs='*',
                   help="Projects to get the names for")

    pa = a.parse_args(*args)

    if not pa.sample_sheet and not pa.proj_numbers:
        exit("You must provide a list of project numbers or else a SampleSheet.csv to scan")
    if pa.update and not pa.yaml:
        exit("If using the --update option, you need to also give a --yaml file")

    return pa

if __name__ == "__main__":
    main(parse_args())
