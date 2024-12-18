#!/usr/bin/env python3
import os, sys, re
from glob import glob
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from packaging.version import parse as parse_version
import yaml, yamlloader

class PostRunMetaData:
    """This Class provides information about a demultiplexing/QC process, given
       a fastqdata folder, to make the file: run_info.{runid}.2.yml
       The info made is supposed to complement the stuff from summarize_for_overview.py
       The following sources will be checked:
         bcl2fastq.version files
         bcl2fastq.info files
         laneN/SampleSheet.filtered.csv
       If you supply a lane only that lane will be checked, otherwise all will be checked.
    """
    def __init__( self , run_folder , fastqdata_path = '', lanes = None, subdir = '.' ):

        self.run_path_folder = os.path.join( fastqdata_path , run_folder )
        self.subdir = subdir
        self.lanes = lanes or []

        self.find_bcl2fastq_versions()
        self.find_bcl2fastq_opts()

        self.find_filtered_samplesheet()

    def find_filtered_samplesheet(self):
        """If there is a filtered version of the sample sheet, take note of it and check
           the #Revcomp, line.
        """
        self.filtered_samplesheet = None
        self.revcomp_setting = None

        if len(self.lanes) != 1:
            # This info only makes sense for a single lane
            return
        single_lane, = self.lanes

        try:
            with open(os.path.join( self.run_path_folder,
                                    self.subdir,
                                    'lane{}'.format(single_lane),
                                    'SampleSheet.filtered.csv' )) as fh:
                self.filtered_samplesheet = [ os.path.basename(fh.name),
                                              os.path.abspath(fh.name) ]
                for l in fh:
                    l = l.rstrip('\n')
                    if l.startswith('[') and l != '[Header]':
                        # We ran past the header section
                        break
                    elif l.startswith('#Revcomp,'):
                        self.revcomp_setting = l.split(',')[1]
                        break
        except FileNotFoundError:
            # OK we don't have one.
            pass

    def find_bcl2fastq_versions(self):
        """If bcl2fastq ran already, the version will be recorded (if there was a cleanup, these files need to
           be purged before this script is run). It's possible we will find multiple versions in different lanes.
        """
        lanes = self.lanes or '*'
        self.bcl2fastq_versions = set()
        for lane in lanes:
            for vf in glob(os.path.join( self.run_path_folder , self.subdir, "lane{}/bcl2fastq.version".format(lane) )):
                with open(vf) as vfh:
                    for aline in vfh:
                        # Version lines look like "bcl2fastq v2.19.1.403"
                        mo = re.match("bcl2fastq v(.*)", aline.rstrip())
                        if mo:
                            self.bcl2fastq_versions.add(mo.group(1))

    def find_bcl2fastq_opts(self):
        """If bcl2fastq ran already, some info will be recorded (if there was a cleanup, these files need to
           be purged before this script is run). It's possible we will find multiple opts in different lanes.
           At the moment we care about --barcode-mismatches and --use-bases-mask
        """
        lanes = self.lanes or '*'
        self.mismatch_flags = set()
        self.bases_mask = set()
        for lane in lanes:
            for vf in glob(os.path.join( self.run_path_folder , self.subdir, f"lane{lane}/bcl2fastq.opts" )):
                actual_lane = vf.split("/")[-2][4:]
                with open(vf) as vfh:
                    for aline in vfh:
                        # Version lines look like "bcl2fastq v2.19.1.403"
                        mo = re.match("--barcode-mismatches +(.*)", aline.rstrip())
                        if mo:
                            self.mismatch_flags.add(mo.group(1))

                        mo = re.match("--use-bases-mask +(.*)", aline.rstrip())
                        if mo:
                            # The mask might begin with "{lane}:" in which case lop that off
                            bm = mo.group(1).strip("'\"")
                            if bm.startswith(f"{actual_lane}:"):
                                bm = bm[2:]
                            self.bases_mask.add(bm)

    def get_yaml(self):

        idict = dict()

        # What version or versions of Illuminatus worked on this run
        version_list = sorted(self.bcl2fastq_versions, key=parse_version)
        idict['post_demux_info'] = {
                'bcl2fastq version': ', '.join(version_list) or 'unknown'
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

        bm = None
        if self.bases_mask:
            if not self.lanes and len(self.bases_mask) > 1:
                # This is for the overview
                bm = "see individual lanes"
            else:
                bm = ', '.join(sorted(self.bases_mask))
        idict['post_demux_info']['bases mask'] = bm or 'not set'

        # Also we want to include the processed sample sheet.
        if self.filtered_samplesheet:
            idict['post_demux_info']['filtered samplesheet'] = self.filtered_samplesheet

        if self.revcomp_setting:
            idict['post_demux_info']['index revcomp'] = self.revcomp_setting

        return yaml.dump( idict,
                          Dumper = yamlloader.ordereddict.CSafeDumper,
                          default_flow_style = False )

def parse_args():
    description = """This script is part of the Illuminatus pipeline.
    It provides some information about a demultiplexing/QC process, given
    a fastqdata folder, and is used to make the files run_info.{runid}.2.yml, one
    per lane and one for the overview page of the MultiQC report.
    The following sources will be checked:
       bcl2fastq.version files
       bcl2fastq.info files
       laneN/SampleSheet.filtered.csv
    You may supply a single lane to check, or else aggregate info for all lanes will
    be scraped.
"""

    a = ArgumentParser( description = description,
                        formatter_class = ArgumentDefaultsHelpFormatter)

    a.add_argument("--fastqdata_path", help="Location of top-level directory where processed runs are found."
                                            " If not specified, script will look in the current working directory.")
    a.add_argument("--run", help="Run to scan", default=".")
    a.add_argument("--lane", help="Lane to scan", default="overview")
    a.add_argument("--subdir", help="Subdirectory where bcl2fastq outputs should be found", default="demultiplexing")

    return a.parse_args()

def main(args):
    # Tinker with the lane argument. In practise we only pass either an empty list
    # or a single lane so scan.

    if args.lane == "overview":
        lanes = []
    elif args.lane.startswith("lane"):
        lanes = [args.lane[4:]]
    else:
        lanes = [args.lane]

    run_info = PostRunMetaData( run_folder = args.run,
                                fastqdata_path = args.fastqdata_path or '',
                                lanes = lanes,
                                subdir = args.subdir )
    print ( run_info.get_yaml() )

if __name__ == '__main__':
    main(parse_args())
