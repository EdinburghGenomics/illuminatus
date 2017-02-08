#!/usr/bin/env python3

import unittest
import sys, os
import glob
from tempfile import mkdtemp
from shutil import rmtree, copytree

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from RunInfo import RunInfo

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')

class TestRunINFO(unittest.TestCase):

    #Helper functions:
    def use_run(self, run_id, copy=False, make_run_info=True):
        """Inspect a run.
           If copy=True, copies a selected run into a temporary folder first.
           Sets self.current_run to the run id and
           self.run_dir to the temporary run dir, temporary or otherwise.
           Also returns a RunInfo object for you.
        """
        self.cleanup_run()

        if copy:
            #Make a temp dir
            self.run_dir = self.tmp_dir = mkdtemp()

            #Clone the run folder into it
            copytree( os.path.join(DATA_DIR, run_id),
                      os.path.join(self.run_dir, run_id),
                      symlinks=True )
        else:
            self.run_dir = DATA_DIR

        #Set the current_run variable
        self.current_run = run_id

        #Presumably we want to inspect the new run, so do that too.
        #If you want to change files around, do that then make a new RunInfo
        #by copying the line below.
        if make_run_info:
            return RunInfo(self.current_run, run_path = self.run_dir)

    def cleanup_run(self):
        """If self.tmp_dir has been set, delete the temporary
           folder. Either way, clear the currently set run.
        """
        if vars(self).get('tmp_dir'):
            rmtree(self.tmp_dir)

        self.run_dir = self.tmp_dir = None
        self.current_run = None

    def tearDown(self):
        """Avoid leaving temp files around.
        """
        self.cleanup_run()

    def test_run_finished( self ):
        """See if the finished/unfinished state of runs is correctly determined.
        """
        run_info = self.use_run('150602_M01270_0108_000000000-ADWKV')
        self.assertFalse( run_info._is_sequencing_finished() )

        run_info = self.use_run('160603_M01270_0196_000000000-AKGDE')
        self.assertTrue( run_info._is_sequencing_finished() )

        run_info = self.use_run('160607_D00248_0174_AC9E4KANXX')
        self.assertFalse( run_info._is_sequencing_finished() )

    def test_is_new_run( self ):
        run_info = self.use_run('150602_M01270_0108_000000000-ADWKV')
        self.assertTrue( run_info._is_new_run() )

        run_info = self.use_run('160603_M01270_0196_000000000-AKGDE')
        self.assertFalse( run_info._is_new_run() )

    def test_in_pipeline( self ):
        run_info = self.use_run('160607_D00248_0174_AC9E4KANXX')
        self.assertTrue( run_info._was_started() )

        run_info = self.use_run('160603_M01270_0196_000000000-AKGDE')
        self.assertFalse( run_info._was_started() )

    def test_is_restarted( self ):
        run_info = self.use_run('160607_D00248_0174_AC9E4KANXX')
        self.assertTrue( run_info._was_restarted() )

        run_info = self.use_run('160606_K00166_0102_BHF22YBBXX')
        self.assertFalse( run_info._was_restarted() )

    def test_is_finished( self ):
        run_info = self.use_run('160607_D00248_0174_AC9E4KANXX')
        self.assertTrue( run_info._was_finished() )

        run_info = self.use_run('160606_K00166_0102_BHF22YBBXX')
        self.assertFalse( run_info._was_finished() )

    def test_get_yaml(self):
        """Ensure that the YAML output is what we expect.
           Don't actually parse the YAML as we don't want the extra dependency.
        """
        run_info = self.use_run('160726_K00166_0120_BHCVH2BBXX', copy=True)

        def dictify(s):
            return dict(zip(s.split()[0::2], s.split()[1::2]))

        expected = dictify("""
            RunID: 160726_K00166_0120_BHCVH2BBXX
            LaneCount: 8
            Instrument: hiseq4000
            Flowcell: HCVH2BBXX
            Status: reads_unfinished
        """)

        self.assertEqual(dictify(run_info.get_yaml()), expected)

        rmtree(os.path.join(self.run_dir, self.current_run, 'pipeline'))

        expected['Status:'] = 'new'
        self.assertEqual(dictify(run_info.get_yaml()), expected)

    def test_status( self ):
        #get status for all run folders
        runs = [ os.path.basename(r) for r in glob.glob(DATA_DIR + '/1*') ]
        for run in runs:

            run_info = self.use_run(run, copy=False)
            #print("%s: %s" % (run, run_info.get_status()) )

            # If copy=True you can safely change files in self.run_dir.
            run_info_new = self.use_run(run, copy=True)
            # or...
            #run_info_new = RunInfo(self.current_run, run_path = self.run_dir)

            #TODO: I'm not suggesting this is a useful test. Just a placeholder.
            self.assertEqual(run_info.get_status(), run_info_new.get_status())

if __name__ == '__main__':
    unittest.main()

