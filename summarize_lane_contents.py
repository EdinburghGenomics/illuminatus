#!/usr/bin/env python3
import sys, os
import datetime
from argparse import ArgumentParser

from illuminatus.SampleSheetReader import SampleSheetReader
from illuminatus.RunInfoXMLParser import RunInfoXMLParser

def parse_args():
    description = """This script is part of the Illuminatus pipeline.
It makes the Samplesheet report that was previously handled by
wiki-communication/bin/upload_run_info_on_wiki.py, by parsing the SampleSheet.csv
and RunInfo.xml in the current directory and by asking the LIMS for proper project
names.
Output may be in YAML, TSV or Text format.
Soon it will ask the LIMS for additional details (loading conc) too.
"""
    a = ArgumentParser(description=description)
    a.add_argument("--project_name_list",
                   help="Supply a comma-separated list of project names." +
                        " If you do this, the LIMS will not be queried." +
                        " You can equivalently setenv PROJECT_NAME_LIST." )
    a.add_argument("--from-yml",
                   help="Get the info from the supplied YAML file, not by" +
                        "scanning the directory and the LIMS." )
    a.add_argument("--yml",
                   help="Output in YAML format to the specified file (- for stdout)." )
    a.add_argument("--txt",
                   help="Output in text format to the specified file (- for stdout)." )
    a.add_argument("--tsv",
                   help="Output in TSV format to the specified file (- for stdout)." )

    a.add_argument("run_dir", nargs='?', default='.',
                   help="Supply a directory to scan, if not the current directory.")

    return a.parse_args()

def printable_date():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def main(args):

    # Load both the RunInfo.xml and the SampleSheet.csv
    try:
        ri_xml = RunInfoXMLParser(args.run_dir + "/RunInfo.xml")
        ss_csv = SampleSheetReader(args.run_dir + "/SampleSheet.csv")
    except FileNotFoundError as e:
        print("Error summarizing run.")
        print(e)
        return

    #Basic metadata, followed be a per-lane summary.
    print( "Run ID: {}".format(ri_xml.run_info['RunId']) )
    print( "Instrument: {}".format(ri_xml.run_info['Instrument']) )
    print( "Read length: {}".format(','.join(
                        [ ('[{}]' if ri_xml.read_and_indexed[i] is 'Y' else '{}'
                          ).format(ri_xml.read_and_length[i])
                          for i in
                          sorted(ri_xml.read_and_length.keys(), key=int) ]
         )) )
    print( "Active SampleSheet: SampleSheet.csv -> {}".format(
                os.path.basename(os.readlink(args.run_dir + "/SampleSheet.csv"))) )
    print( )

    #Translate all the projects in one go
    project_name_list = ( args.project_name_list or os.environ.get('PROJECT_NAME_LIST', '') )

    prn = project_real_name( set([ line[ss_csv.column_mapping['sample_project']]
                                   for line in ss_csv.samplesheet_data ]),
                             project_name_list.split(',') )

    print("Samplesheet report at {}:".format(printable_date()))

    #Slice the sample sheet by lane
    ss_lanes = [ line[ss_csv.column_mapping['lane']] for line in ss_csv.samplesheet_data ]
    for lane in sorted(set(ss_lanes)):
        print( "Lane {}:".format(lane) )
        print( summarize_lane([ line for line in ss_csv.samplesheet_data
                                if line[ss_csv.column_mapping['lane']] == lane ],
                              ss_csv.column_mapping, prn) )

def summarize_lane(lane_lines, column_mapping, prn):
    """Given a list of lines, summarize what they contain.
       The caller is presumed to have filtered them by lane.
    """
    res = []

    projects = [ line[column_mapping['sample_project']] for line in lane_lines ]

    for project in sorted(set(projects)):

        proj_lines =  [ line for line in lane_lines
                        if line[column_mapping['sample_project']] == project ]

        #Libraries actually taken from the 'description' column.
        lib_list = [line[column_mapping['description']] for line in proj_lines]

        res.append( "    - Project {p} -- Library {l} -- Number of indexes {ni} ".format(
                            p  = project,
                            l  = ','.join(sorted(set(lib_list))),
                            ni = len(proj_lines)
                    ) )
        res.append( "    - See {link}".format(link = prn[project].get('url', prn[project]['name'])) )

    return "\n".join(res)


# A rather contorted way to get project names. We may be able to bypass
# this by injecting them straight into the sample sheet!
def project_real_name(proj_id_list, name_list=None):
    """Resolves a list of project IDs to a name and URL
    """
    res = dict()
    if name_list:
        # Resolve without going to the LIMS. Note that if you want to disable
        # LIMS look-up without supplying an actuall list of names you can just
        # say "--project_names dummy" or some such thing.
        for p in proj_id_list:
            name_match = [ n for n in name_list if n.startswith(p) ]
            if len(name_match) == 1:
                res[p] = dict( name = name_match[0],
                               url  = "http://foo.example.com/" + name_match[0] )
            else:
                res[p] = dict( name = p + "_UNKNOWN" )
    else:
        try:
            from illuminatus.LIMSQuery import get_project_names

            for p, n in zip(proj_id_list, get_project_names(*proj_id_list)):
                if n:
                    res[p] = dict( name = n,
                                   url = "http://foo.example.com/" + name_match[0] )
                else:
                    res[p] = dict( name = p + "_UNKNOWN" )
        except Exception as e:
            for p in proj_id_list:
                if p not in res:
                    res[p] = dict( name = p + "_LOOKUP_ERROR",
                                   url = "error://" + repr(e) )

    return res

if __name__ == "__main__":
    main(parse_args())
