#!/usr/bin/env python3

"""Test the do_demultiplex.sh script"""

import sys, os, re
import unittest
import logging

from bashmocker import BashMocker
from sandbox import TestSandbox

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/samplesheet_filtered_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

DEMUX_SCRIPT = os.path.abspath(os.path.dirname(__file__) + '/../do_demultiplex.sh')

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

        # Initialise the binmocker
        self.bm = BashMocker()
        self.bm.add_mock( 'bcl2fastq',
                          side_effect = 'echo 123 >&2' )

        # A temp dir for output logs
        self.tmp_dir = TestSandbox()

    def tearDown(self):
        # Clean up the binmocker
        self.bm.cleanup()

        # Clean the temp dir
        self.tmp_dir.cleanup()

    def get_example(self, foo):
        return os.path.join(DATA_DIR, "SampleSheet.filtered.{}.csv".format(foo))

    def bm_rundemux(self, args, expected_retval=0, check_stderr=True):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs the script and returns STDOUT split into an array.
        """
        retval = self.bm.runscript( [DEMUX_SCRIPT] + args,
                                    set_path = True )

        #Where a file is missing it's always useful to see the error.
        #(status 127 is the standard shell return code for a command not found)
        if retval == 127 or VERBOSE:
            print("STDERR:")
            print(self.bm.last_stderr)
        if VERBOSE:
            print("STDOUT:")
            print(self.bm.last_stdout)
            print("RETVAL: %s" % retval)

        self.assertEqual(retval, expected_retval)

        # stderr should be empty, unless we say it shouldn't
        if check_stderr:
            self.assertEqual(self.bm.last_stderr, '')

        return self.bm.last_stdout.split("\n")

    ### THE TESTS ###
    def test_miseq_demux(self):
        """A standard demultiplex with barcode-mismatches set to 1
        """
        res = self.bm_rundemux([ 'dummy_seqdata',
                                 self.tmp_dir.sandbox,
                                 self.get_example('1'),
                                 '1' ])

        # bcl2fastq should be called with appropriate args
        self.assertEqual(self.bm.last_calls, dict( bcl2fastq = [
                        ['--version'],
                        ['-R', 'dummy_seqdata', '-o', self.tmp_dir.sandbox,
                         '--fastq-compression-level', '6',
                         '--use-bases-mask', '1:Y100n,I8,I8,Y100n',
                         '--tiles=s_[1]',
                         '--barcode-mismatches', '1',
                         '--sample-sheet', self.get_example('1'),
                         '-p', '10'] ]))


        # log and version should be empty
        self.assertEqual( self.tmp_dir.lsdir('.'), ['bcl2fastq.log', 'bcl2fastq.opts', 'bcl2fastq.version'] )

        # bcl2fastq.opts should have 4 lines
        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.opts')) as fh:
            self.assertEqual(len(list(fh)), 4)

    def test_bad_bcl2fastq(self):
        """If bcl2fastq won't run at all, even to give a version
        """
        self.bm.add_mock( 'bcl2fastq', fail=True )

        res = self.bm_rundemux( [ 'dummy_seqdata',
                                  self.tmp_dir.sandbox,
                                  self.get_example('1'),
                                  '1' ],
                                expected_retval = 1 )

        self.assertEqual(self.bm.last_calls, dict( bcl2fastq = [ ['--version'] ] ))

    def test_fail_demux(self):
        """And if demultiplexing fails?
        """
        # Here I need a dummy bcl2fastq that will print a version but fail otherwise
        self.bm.add_mock( 'bcl2fastq',
                          side_effect = 'if [ $1 = --version ] ; then echo 123 ; exit 0 ; else exit 1 ; fi' )

        res = self.bm_rundemux( [ 'dummy_seqdata',
                                  self.tmp_dir.sandbox,
                                  self.get_example('1'),
                                  '1' ],
                                expected_retval = 1 )

        # No .opts file written on failure.
        self.assertEqual( self.tmp_dir.lsdir('.'), ['bcl2fastq.log', 'bcl2fastq.version'] )

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.version')) as fh:
            self.assertEqual(list(fh), ['123\n'])

    def test_fail_demux_n(self):
        """And if demultiplexing fails without --barcode-mismatches supplied?
           This should run the same as test_fail_demux
        """
        # Here I need a dummy bcl2fastq that will print a version but fail otherwise
        self.bm.add_mock( 'bcl2fastq',
                          side_effect = 'if [ $1 = --version ] ; then echo 123 ; exit 0 ; else exit 1 ; fi' )

        res = self.bm_rundemux( [ 'dummy_seqdata',
                                  self.tmp_dir.sandbox,
                                  self.get_example('N'),
                                  '1' ],
                                expected_retval = 1 )

        # No .opts file written on failure. No mismatch1.log because the failure is not a
        # collision failure.
        self.assertEqual( self.tmp_dir.lsdir('.'), ['bcl2fastq.log', 'bcl2fastq.version'] )

        self.assertEqual(self.bm.last_calls, dict( bcl2fastq = [
                        ['--version'],
                        ['-R', 'dummy_seqdata', '-o', self.tmp_dir.sandbox,
                         '--fastq-compression-level', '6',
                         '--use-bases-mask', '1:Y100n,I8,I8,Y100n',
                         '--tiles=s_[1]',
                         '--sample-sheet', self.get_example('N'),
                         '-p', '10',
                         '--barcode-mismatches', '1' ] ]))

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.version')) as fh:
            self.assertEqual(list(fh), ['123\n'])

    def test_demux_auto_mismatch(self):
        """A run that fails at mismatch 1 then works at mismatch 0
        """
        # Now I need a dummy bcl2fastq that will print a version AND succeed if
        # --barcode-mismatches 0 is supplied...

        self.bm.add_mock( 'bcl2fastq',
                          side_effect = 'if [ $1 = --version ] ;'
                                        '  then echo 123 >&2 ; exit 0 ;'
                                        'elif grep -q -- "--barcode-mismatches 0" <<<"$*" ;'
                                        '  then echo OK >&2 ; exit 0 ;'
                                        'else '
                                        '  echo "Barcode collision for barcodes: XXX" >&2 ; exit 1 ;'
                                        'fi' )

        res = self.bm_rundemux( [ 'dummy_seqdata',
                                  self.tmp_dir.sandbox,
                                  self.get_example('N'),
                                  '1' ],
                                expected_retval = 0 )

        self.assertEqual( self.tmp_dir.lsdir('.'), [ 'bcl2fastq.log',
                                                     'bcl2fastq.opts',
                                                     'bcl2fastq.version',
                                                     'bcl2fastq_mismatch1.log' ] )

        self.assertEqual(self.bm.last_calls, dict( bcl2fastq = [
                        ['--version'],
                        ['-R', 'dummy_seqdata', '-o', self.tmp_dir.sandbox,
                         '--fastq-compression-level', '6',
                         '--use-bases-mask', '1:Y100n,I8,I8,Y100n',
                         '--tiles=s_[1]',
                         '--sample-sheet', self.get_example('N'),
                         '-p', '10',
                         '--barcode-mismatches', '1',
                         ],
                        ['-R', 'dummy_seqdata', '-o', self.tmp_dir.sandbox,
                         '--fastq-compression-level', '6',
                         '--use-bases-mask', '1:Y100n,I8,I8,Y100n',
                         '--tiles=s_[1]',
                         '--sample-sheet', self.get_example('N'),
                         '-p', '10',
                         '--barcode-mismatches', '0',
                         ] ]))

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.version')) as fh:
            self.assertEqual(list(fh), ['123\n'])

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq_mismatch1.log')) as fh:
            self.assertEqual(list(fh), ['Barcode collision for barcodes: XXX\n'])

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.log')) as fh:
            self.assertEqual(list(fh), ['OK\n'])

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.opts')) as fh:
            self.assertEqual([l.rstrip('\n') for l in list(fh)], [
                            "--barcode-mismatches 0",
                            "--fastq-compression-level 6",
                            "--use-bases-mask '1:Y100n,I8,I8,Y100n'",
                            "--tiles=s_[$LANE]",
                            ])

    def test_fail_demux_both(self):
        """A run that reports collisions with either setting
        """
        # Here I need a dummy bcl2fastq that will print a version but feign
        # a collision otherwise.
        self.bm.add_mock( 'bcl2fastq',
                          side_effect = 'if [ $1 = --version ] ; then echo 123 ; exit 0 ;'
                                        ' else echo "Barcode collision for barcodes: XXX" >&2 ; exit 1 ; fi' )

        res = self.bm_rundemux( [ 'dummy_seqdata',
                                  self.tmp_dir.sandbox,
                                  self.get_example('N'),
                                  '1' ],
                                expected_retval = 1 )

        # No .opts file written on failure.
        self.assertEqual( self.tmp_dir.lsdir('.'), ['bcl2fastq.log', 'bcl2fastq.version', 'bcl2fastq_mismatch1.log'] )

        with open(os.path.join(self.tmp_dir.sandbox, 'bcl2fastq.version')) as fh:
            self.assertEqual(list(fh), ['123\n'])

if __name__ == '__main__':
    unittest.main()
