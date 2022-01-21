#!/usr/bin/env python3

import sys, os
import unittest
import xml.etree.ElementTree as ET

from snakemake.workflow import Workflow

""" Can I unit test a Snakefile?
    Of course I can!
    Or, at least, I can test any functions defined at the top level.
    Importing the functions from the Snakefile requres parsing it with the
    Snakemake internals, and setting a couple of environment things.
"""
DATA_DIR = os.path.abspath(os.path.dirname(__file__))
def get_ex(runid):
    """Get the 2 args needed by get_wd_settings
    """
    run_path = os.path.join(DATA_DIR, 'seqdata_examples', runid)
    return ( run_path,
             ET.parse(run_path + "/RunInfo.xml").getroot() )

os.environ['TOOLBOX'] = 'dummy'
sf = os.path.join(os.path.dirname(__file__), '..', 'Snakefile.read1qc')
wf = Workflow(sf, overwrite_config=dict())
wf.include(sf)

# I can now import top-level functions like so:
get_wd_settings = wf.globals['get_wd_settings']

class T(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_get_wd_miseq(self):
        """Getting WD settings for a MiSeq run should obtain an empty lane list,
           as WD scanning makes no sense on these flowcells.
        """
        self.assertEqual(
            get_wd_settings(*get_ex('160603_M01270_0196_000000000-AKGDE')),
            dict( TARGETS_TO_SAMPLE = 2500,
                  READ_LENGTH = 50,
                  START_POS = 20,
                  END_POS = 0,
                  LEVELS_TO_SCAN = 5,
                  REPORT_VERBOSE = True,
                  FIRST_TILE = '0000',
                  LAST_TILE = '0000',
                  LANES_IN_RUN = [1],
                  LAST_LANE = '0',
                  TILE_MATCH = {} ) )

    def test_get_wd_novo(self):
        """A couple of NovoSeq runs with short read cycles
        """
        # 51 bp reads, dual index
        # LAST_TILE > 2400 so we only scan half the tiles
        self.assertEqual(
            get_wd_settings(*get_ex('180619_A00291_0044_BH5WJJDMXX')),
            dict( TARGETS_TO_SAMPLE = 2500,
                  READ_LENGTH = 50,
                  START_POS = 0,
                  END_POS = 50,
                  LEVELS_TO_SCAN = 5,
                  REPORT_VERBOSE = True,
                  FIRST_TILE = '1101',
                  LAST_TILE = '2488',
                  LANES_IN_RUN = [1,2],
                  LAST_LANE = '2',
                  TILE_MATCH = {'B': '2..[02468]', 'T': '1..[02468]'} ) )

        # Run with a short first read. Scan needs to happen on the second read.
        # As this is a SP and LAST_TILE < 2400 we scan all the tiles
        self.assertEqual(
            get_wd_settings(*get_ex('210722_A00291_0378_AHFT2CDRXY')),
            dict( TARGETS_TO_SAMPLE = 2500,
                  READ_LENGTH = 50,
                  START_POS = 36,
                  END_POS = 86,
                  LEVELS_TO_SCAN = 5,
                  REPORT_VERBOSE = True,
                  FIRST_TILE = '1101',
                  LAST_TILE = '2278',
                  LANES_IN_RUN = [1,2],
                  LAST_LANE = '2',
                  TILE_MATCH = {'B': '2...', 'T': '1...'} ) )

    def test_get_wd_sp(self):
        """Getting WD settings for a SP run should only be scanning one
           surface.
        """
        self.assertEqual(
            get_wd_settings(*get_ex('210903_A00291_0383_BHCYNNDRXY')),
            dict( TARGETS_TO_SAMPLE = 2500,
                  READ_LENGTH = 50,
                  START_POS = 20,
                  END_POS = 70,
                  LEVELS_TO_SCAN = 5,
                  REPORT_VERBOSE = True,
                  FIRST_TILE = '2101',
                  LAST_TILE = '2278',
                  LAST_LANE = '2',
                  LANES_IN_RUN = [1,2],
                  TILE_MATCH = {'B': '2...'} ) )

    def test_get_wd_slim(self):
        """Getting WD settings for a slimmed run should take note of the only
           selected tile in pipeline_settings.ini
        """
        self.assertEqual(
            get_wd_settings(*get_ex('220113_A00291_0410_AHV23HDRXY')),
            dict( TARGETS_TO_SAMPLE = 2500,
                  READ_LENGTH = 50,
                  START_POS = 20,
                  END_POS = 70,
                  LEVELS_TO_SCAN = 5,
                  REPORT_VERBOSE = True,
                  FIRST_TILE = '2101',
                  LAST_TILE = '2278',
                  LAST_LANE = '2',
                  LANES_IN_RUN = [1,2],
                  TILE_MATCH = {'B': '2101'} ) )
if __name__ == '__main__':
    unittest.main()

