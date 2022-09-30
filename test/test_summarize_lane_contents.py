#!/usr/bin/env python3

import unittest
import sys, os, re
from glob import glob
from pprint import pprint
import io

from summarize_lane_contents import project_real_name, scan_for_info, yaml, \
        output_yml, output_tsv, output_txt, output_mqc

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')
LC_DIR =  os.path.abspath(os.path.dirname(__file__) + '/summarize_lane_contents')

class T(unittest.TestCase):

    def setUp(self):
        # Placeholder for fromatted content
        self.formatted = { k: None for k in 'yml mqc txt tsv'.split() }
        self.formatted_as_list = self.formatted.copy()

        self.maxDiff = None

    def test_name_lookup(self):
        """Test the name lookup logic
        """

        res = project_real_name(['123', '456'], name_list='123_Example_Project')

        #Ignore the url value for now. Or rather, just test it exists.
        self.assertEqual( res,
                          { '123' : dict( name = '123_Example_Project',
                                          url = res['123']['url'] ),
                            '456' : dict( name = '456_UNKNOWN' )        })

        # TODO - test mock LIMS connection

    def test_date_conversion(self):
        """Test the date formatting logic for rids['RunDate']
           on a few examples. Actually this comes from the RunParametersXMLParser
           so the unit test should really be at that level.
        """
        self.scan_project(DATA_DIR + '/210722_A00291_0378_AHFT2CDRXY')
        self.assertEqual(self.rids['RunDate'], '2021-07-22')

        self.scan_project(DATA_DIR + '/210827_M05898_0165_000000000-JVM38')
        self.assertEqual(self.rids['RunDate'], '2021-08-27')

        # This one was broken. But now fixed.
        self.scan_project(DATA_DIR + '/210903_A00291_0383_BHCYNNDRXY')
        self.assertEqual(self.rids['RunDate'], '2021-09-03')

    def test_scan_project(self):

        self.scan_project(LC_DIR + '/170221_K00166_0183_AHHT3HBBXX')

        # Check there was output for all things
        self.assertTrue( all( self.formatted.values() ))

        # Check the samplesheet is reported right
        self.assertRegex( 'txt', r'Active SampleSheet:.*?(\S+$)', [ 'SampleSheet.csv.1' ] )

        # Check that the RunStartTimeStamp is being set correctly - just look in rids
        self.assertEqual( self.rids['RunStartTime'], 'Fri 08-Sep-2017 13:36:55')
        self.assertEqual( self.rids['RunStartTimeStamp'], 1504874215 )
        self.assertEqual( type(self.rids['RunStartTimeStamp']), int )

    def test_scan_allprojects(self):
        """ Not all the projects we have in the examples dir are suitable to be scanned.
            But some are.
            TODO - add at least a MiSeq run.
        """
        for d in (DATA_DIR + '/160614_K00368_0023_AHF724BBXX',
                  DATA_DIR + '/160606_K00166_0102_BHF22YBBXX' ):

            proj = os.path.basename(d.rstrip('./'))

            try:
                self.scan_project(d)
            except:
                print("Exception while scanning project {}.".format( proj ))
                raise

            self.assertTrue( all( self.formatted.values() ),
                            "Did not get all values for project {} -- {}".format(
                                 proj, self.formatted ))


    def test_load_from_yml(self):

        self.scan_project(LC_DIR + '/170221_K00166_0183_AHHT3HBBXX.yml')

        # At present, just check there was output
        self.assertTrue( all( self.formatted.values() ))

    def test_all_addins(self):
        """ Added after I got the wrong value for the number of raw clusters on
            my QC report. I need test coverage for the addins anyway.
            Basically, trust the b2f value over the InterOP.
        """
        proj_dir = LC_DIR + '/180209_E00397_0086_AHHMYHCCXY'
        self.scan_project(proj_dir + '/sample_summary.yml',
                            addins = { 'wd':    proj_dir + '/2500summary.yml',
                                       'b2f':   proj_dir + '/bcl2fastq_stats.yml',
                                       'yield': proj_dir + '/yield.yml' } )

        # The mqc.yaml should be as per the sample provided
        with open(LC_DIR + '/180209_E00397_0086_AHHMYHCCXY/ls_mqc.yaml') as yfh:
           sample_mqc_yml = yaml.safe_load(yfh)

        self.assertEqual(sample_mqc_yml, yaml.safe_load(self.formatted['mqc']))

    def test_some_addins(self):
        """ Added after I got the wrong value for the number of raw clusters on
            my QC report. I need test coverage for the addins anyway.
            Here we do not have the b2f data, so take the total clusters
            from the IterOP. Otherwise as above.
        """
        proj_dir = LC_DIR + '/180209_E00397_0086_AHHMYHCCXY'
        self.scan_project(proj_dir + '/sample_summary.yml',
                            addins = { 'wd':    proj_dir + '/2500summary.yml',
                                       'b2f':   None,
                                       'yield': proj_dir + '/yield.yml' } )

        # The mqc.yaml should be as per the sample provided
        with open(LC_DIR + '/180209_E00397_0086_AHHMYHCCXY/ls_nob2f_mqc.yaml') as yfh:
           sample_mqc_yml = yaml.safe_load(yfh)

        self.assertEqual(sample_mqc_yml, yaml.safe_load(self.formatted['mqc']))

    def assertRegex(self, output, regex, expected):
        """Assertion based on regexes
        """
        search_list = self.formatted_as_list[output]

        matches = [ mo.group(1) for mo in
                    [ re.match(regex, line) for line in search_list ]
                    if mo ]

        self.assertEqual(matches, expected)

    def scan_project(self, fname, addins=None):
        """Scan a project folder and do all the conversions at once.
           Dummy name-list of '-' will be set to avoid LIMS look-ups.
           Text output will be captured to out_buf so if a test wants to examine
           the contents it needs to re-parse it.
        """
        if os.path.isdir(fname):
            rids = scan_for_info(fname, '-')
        else:
            with open(fname) as yfh:
                rids = yaml.safe_load(yfh)

        # Add-ins
        for key, filename in (addins or {}).items():
            if filename:
                with open(filename) as gfh:
                    rids['add_in_' + key] = yaml.safe_load(gfh)

        for formatter in list(self.formatted):
            out_buf = io.StringIO()
            globals()['output_'+formatter](rids, out_buf)

            self.formatted[formatter] = out_buf.getvalue()
            self.formatted_as_list[formatter] = out_buf.getvalue().rstrip('\n').split('\n')

            out_buf.close()

        # Grab the rids too
        self.rids = rids

if __name__ == '__main__':
    unittest.main()
