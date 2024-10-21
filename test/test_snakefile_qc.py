#!/usr/bin/env python3

import sys, os
import unittest

# FIXME - in Snakemake 8 this is totally different.
from snakemake.workflow import Workflow

""" Can I unit test a Snakefile?
    Of course I can!
    Or, at least, I can test any functions defined at the top level.
    Importing the functions from the Snakefile requres parsing it with the
    Snakemake internals, and setting a couple of environment things.
"""
os.environ['TOOLBOX'] = 'dummy'
sf = os.path.join(os.path.dirname(__file__), '..', 'Snakefile.qc')
wf = Workflow(sf, overwrite_config=dict(runid='170221_K00166_0183_AHHT3HBBXX'))
wf.include(sf)

# I can now import top-level functions like so:
split_fq_name = wf.globals['split_fq_name']

class T(unittest.TestCase):

    def test_split_fq_name(self):
        """Test the function which claims to work as follows...
            Break out components from the name of a a FASTQ file.
                eg. 10749/10749DMpool03/170221_K00166_0183_AHHT3HBBXX_8_10749DM0001L01_1.fastq.gz
                eg. 170221_K00166_0183_AHHT3HBBXX_1_unassigned_1.fastq.gz
        """
        # eg. 1
        self.assertEqual(
            split_fq_name('10749/10749DMpool03/170221_K00166_0183_AHHT3HBBXX_8_10749DM0001L01_1.fastq.gz'),
            dict( proj  = '10749',
                  pool  = '10749DMpool03',
                  fname = '10749/10749DMpool03/170221_K00166_0183_AHHT3HBBXX_8_10749DM0001L01_1',
                  bname = '170221_K00166_0183_AHHT3HBBXX_8_10749DM0001L01_1',
                  run   = '170221_K00166_0183_AHHT3HBBXX',
                  lane  = '8',
                  lib   = '10749DM0001L01',
                  read  = '1',
                  unassigned = False ) )

        # eg. 2
        self.assertEqual(
            split_fq_name('170221_K00166_0183_AHHT3HBBXX_1_unassigned_1.fastq.gz'),
            dict( proj  = None,
                  pool  = None,
                  fname = '170221_K00166_0183_AHHT3HBBXX_1_unassigned_1',
                  bname = '170221_K00166_0183_AHHT3HBBXX_1_unassigned_1',
                  run   = '170221_K00166_0183_AHHT3HBBXX',
                  lane  = '1',
                  lib   = None,
                  read  = '1',
                  unassigned = True ) )

if __name__ == '__main__':
    unittest.main()

