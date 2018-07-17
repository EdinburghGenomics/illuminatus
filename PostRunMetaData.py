#!/usr/bin/env python3
import os, sys, re
from glob import glob

import yaml

class PostRunMetaData:
    """This Class provides information about a demultiplexing/QC process, given
       a fastqdata folder.
       The info made is supposed to complement the stuff from RunMetaData.py.
       The following sources will be checked:
         bcl2fastq.version files
         bcl2fastq.info files
       If you supply a lane only that lane will be checked, otherwise all will be checked.
    """
    def __init__( self , run_folder , fastqdata_path = '', lanes = None ):

        self.run_path_folder = os.path.join( fastqdata_path , run_folder )
        self.lanes = lanes

        self.find_bcl2fastq_versions()
        self.find_bcl2fastq_opts()

    def find_bcl2fastq_versions(self):
        """If bcl2fastq ran already, the version will be recorded (if there was a cleanup, these files need to
           be purged before this script is run). It's possible we will find multiple versions in different lanes.
        """
        lanes = self.lanes or '*'
        self.bcl2fastq_versions = set()
        for lane in lanes:
            for vf in glob(os.path.join( self.run_path_folder , 'demultiplexing/lane{}/bcl2fastq.version'.format(lane) )):
                with open(vf) as vfh:
                    for aline in vfh:
                        # Version lines look like "bcl2fastq v2.19.1.403"
                        mo = re.match("bcl2fastq v(.*)", aline.rstrip())
                        if mo:
                            self.bcl2fastq_versions.add(mo.group(1))

    def find_bcl2fastq_opts(self):
        """If bcl2fastq ran already, some info will be recorded (if there was a cleanup, these files need to
           be purged before this script is run). It's possible we will find multiple opts in different lanes.
           At the moment we only care about --barcode-mismatches
        """
        lanes = self.lanes or '*'
        self.mismatch_flags = set()
        for lane in lanes:
            for vf in glob(os.path.join( self.run_path_folder , 'demultiplexing/lane{}/bcl2fastq.opts'.format(lane) )):
                with open(vf) as vfh:
                    for aline in vfh:
                        # Version lines look like "bcl2fastq v2.19.1.403"
                        mo = re.match("--barcode-mismatches +(.*)", aline.rstrip())
                        if mo:
                            self.mismatch_flags.add(mo.group(1))

    def get_yaml(self):

        idict = dict()

        # Only one thing to report for now, but I'm sure there will be more.
        idict['post_demux_info'] = {
                'bcl2fastq version': ', '.join(sorted(self.bcl2fastq_versions)) or 'unknown'
            }

        # I thought about adding the pipeline finish time, but it doesn't belong here.
        # We can use the time the final report is generated.

        # But we do want to know how the mismatch flag was set
        mf = None
        if self.mismatch_flags:
            if not self.lanes:
                # This is for the overview
                # "standard (1)" or "exact (0)" or "see individual lanes"
                if self.mismatch_flags == set('0'):
                    mf = "exact (0)"
                elif self.mismatch_flags == set('1'):
                    mf = "standard (1)"
                else:
                    mf = "see individual lanes"
            else:
                mf = ', '.join(self.mismatch_flags)
        idict['post_demux_info']['barcode mismatches'] = mf or 'unknown'

        return yaml.safe_dump(idict, default_flow_style=False)

def munge_lanes(l):
    """Take the lanes arguments and return a dict {'lanes': [int, int, int]} or else
       an empty dict - ie. converts sys.argv to **kwargs format.
    """
    res = dict(lanes=[])
    for al in l:
        if al.startswith('lane'):
            res['lanes'].append(al[4:])
        elif al == 'overview':
            # special case
            return {}
        else:
            res['lanes'].append(al)
    return res if res['lanes'] else {}


if __name__ == '__main__':
    #If no run specified, examine the CWD.
    run = sys.argv[1] if len(sys.argv) > 1 else '.'
    run_info = PostRunMetaData(run, **munge_lanes(sys.argv[2:]) )
    print ( run_info.get_yaml() )
