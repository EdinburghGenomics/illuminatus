#!/usr/bin/env python3

import unittest
import sys, os, re
from glob import glob
from pprint import pprint
import io

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')

from summarize_lane_contents import project_real_name, scan_for_info, yaml, \
        output_yml, output_tsv, output_txt, output_mqc

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')
LC_DIR =  os.path.abspath(os.path.dirname(__file__) + '/summarize_lane_contents')

class T(unittest.TestCase):

    def setUp(self):
        # Placeholder for fromatted content
        self.formatted = { k: None for k in 'yml mqc txt tsv'.split() }
        self.formatted_as_list = self.formatted.copy()

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

    def test_scan_project(self):

        self.scan_project(LC_DIR + '/170221_K00166_0183_AHHT3HBBXX')

        # Check there was output for all things
        self.assertTrue( all( self.formatted.values() ))

        # Check the samplesheet is reported right
        self.assertRegex( 'txt', r'Active SampleSheet:.*?(\S+$)', [ 'SampleSheet.csv.1' ] )

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

    def assertRegex(self, output, regex, expected):
        """Assertion based on regexes
        """
        search_list = self.formatted_as_list[output]

        matches = [ mo.group(1) for mo in
                    [ re.match(regex, line) for line in search_list ]
                    if mo ]

        self.assertEqual(matches, expected)

    def scan_project(self, fname):
        """Scan a project folder and do all the conversions at once.
           Dummy name-list will be set to avoid LIMS look-ups.
        """
        if os.path.isdir(fname):
            rids = scan_for_info(fname, '-')
        else:
            with open(fname) as yfh:
                rids = yaml.safe_load(yfh)

        for formatter in list(self.formatted):
            out_buf = io.StringIO()
            globals()['output_'+formatter](rids, out_buf)

            self.formatted[formatter] = out_buf.getvalue()
            self.formatted_as_list[formatter] = out_buf.getvalue().rstrip('\n').split('\n')

            out_buf.close()


if __name__ == '__main__':
    unittest.main()
