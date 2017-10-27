#!/usr/bin/env python3
import os, sys, re
from glob import glob
from collections import defaultdict
from datetime import datetime

import yaml

class PostRunMetaData:
    """This Class provides information about a demultiplexing/QC process, given
       a fastqdata folder.
       The info made is supposed to complement the stuff from RunMetaData.py.
       The following sources will be checked:
         bcl2fastq.version files
       If you supply a lane only that lane will be checked.
    """
    def __init__( self , run_folder , fastqdata_path = '', lanes = ('*',) ):

        self.run_path_folder = os.path.join( fastqdata_path , run_folder )

        # If bcl2fastq ran already, the version will be recorded (if there was a cleanup, these files need to
        # be purged before this script is run). It's possible we will find multiple versions in different lanes.
        self.bcl2fastq_versions = set()
        for lane in lanes:
            for vf in glob(os.path.join( self.run_path_folder , 'demultiplexing/lane{}/bcl2fastq.version'.format(lane) )):
                with open(vf) as vfh:
                    for aline in vfh:
                        # Version lines look like "bcl2fastq v2.19.1.403"
                        mo = re.match("bcl2fastq v(.*)", aline.rstrip())
                        if mo:
                            self.bcl2fastq_versions.add(mo.group(1))

    def get_yaml(self):

        idict = dict()

        # Only one thing to report for now, but I'm sure there will be more.
        idict['post_demux_info'] = {
                'bcl2fastq version': ', '.join(sorted(self.bcl2fastq_versions)) or 'unknown'
            }

        return yaml.safe_dump(idict, default_flow_style=False)

def munge_lanes(l):
    """Take the lanes arguments and return a dict {'lanes': [int, int, int]} or else
       an empty dict.
    """
    res = dict(lanes=[])
    for al in l:
        if al.startswith('lane'):
            res['lanes'].append(al[4:])
        elif al == 'overview':
            return {}
        else:
            res['lanes'].append(al)
    return res if res['lanes'] else {}


if __name__ == '__main__':
    #If no run specified, examine the CWD.
    run = sys.argv[1] if len(sys.argv) > 1 else '.'
    run_info = PostRunMetaData(run, **munge_lanes(sys.argv[2:]) )
    print ( run_info.get_yaml() )
