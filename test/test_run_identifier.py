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

class T(unittest.TestCase):

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

    def test_read_states_4000(self):
        """Ensure that the YAML output is what we expect.
           Don't fully parse the YAML as we don't want the extra dependency.
        """
        run_info = self.use_run('160726_K00166_0120_BHCVH2BBXX', copy=True)


        expected = dictify("""
            RunID: 160726_K00166_0120_BHCVH2BBXX
            LaneCount: 8
            Instrument: hiseq4000_K00166
            Flowcell: HCVH2BBXX
            PipelineStatus: reads_unfinished
            MachineStatus: waiting_for_data
        """)

        self.assertEqual(dictify(run_info.get_yaml()), expected)

        self.rm('pipeline')

        expected['PipelineStatus:'] = 'new'
        self.assertEqual(dictify(run_info.get_yaml()), expected)

        # We're basing the read1 trigger on the appearance of data files for the second cycle,
        # (until we change our minds and use the first cycle after the last index read)
        # so for this run we need to fake something for cycle 152.
        self.md('Data/Intensities/BaseCalls/L001/C152.1')
        self.touch('Data/Intensities/BaseCalls/L001/C152.1/foo.bcl')

        # Should still be new until we put the pipeline dir back!
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'new')
        self.assertEqual(dictify(run_info.get_yaml())['MachineStatus:'], 'read1_complete')
        self.md('pipeline')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'read1_finished')

        # For this one, let's say that read processing completes before the run finishes.
        self.touch('pipeline/read1.started')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'in_read1_qc')

        # And the read1 processing finishes
        self.touch('pipeline/read1.done')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'reads_unfinished')

        # Now we finish the reads
        self.touch('RTAComplete.txt')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'reads_finished')
        self.assertEqual(dictify(run_info.get_yaml())['MachineStatus:'], 'complete')

        # And we start the demultiplexing
        self.touch('pipeline/lane1.started')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'in_demultiplexing')

        self.touch('pipeline/lane1.done')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'demultiplexed')

    def test_read_states_miseq(self):
        """Ensure that the YAML output is what we expect (for a MiSeq run),
           and run through the states until sequencing finished.
           Don't fully parse the YAML as we don't want the extra dependency.
        """
        run_info = self.use_run('160805_M01145_0035_000000000-ATDYJ', copy=True)

        expected = dictify("""
            RunID: 160805_M01145_0035_000000000-ATDYJ
            LaneCount: 1
            Instrument: miseq_M01145
            Flowcell: ATDYJ
            PipelineStatus: new
            MachineStatus: waiting_for_data
        """)

        self.assertEqual(dictify(run_info.get_yaml()), expected)

        # Add the pipeline dir
        self.md('pipeline')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'reads_unfinished')

        # We're basing the read1 trigger on the appearance of data files for the second cycle,
        # (until we change our minds and use the first cycle after the last index read)
        # so for this run we need to fake something for cycle 27.
        self.md('Data/Intensities/BaseCalls/L001/C27.1')
        self.touch('Data/Intensities/BaseCalls/L001/C27.1/foo.bcl')

        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'read1_finished')

        # Adding an RTAComplete.txt file should not change this status
        self.touch('RTAComplete.txt')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'read1_finished')

        # Adding read1.started should push us to the state where ops will trigger in parallel
        self.touch('pipeline/read1.started')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'in_read1_qc_reads_finished')

        # Adding read1.done should get us to reads_finished
        self.touch('pipeline/read1.done')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'reads_finished')

        self.touch('pipeline/lane1.started')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'in_demultiplexing')

        self.touch('pipeline/lane1.done')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'demultiplexed')

        # OK, but if the read1.done file never appeared we should still be in in_read1_qc
        self.rm('pipeline/read1.done')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'in_read1_qc')

        # And if the read1.started file vanishes we go right back to read1_finished,
        # as QC should not start until both read1 and demultiplexing are done.
        # Though in practise this state should not happen.
        self.rm('pipeline/read1.started')
        self.assertEqual(dictify(run_info.get_yaml())['PipelineStatus:'], 'read1_finished')



    @unittest.skip
    def test_pointless_copying(self):
        """This test is not yet very useful
        """
        runs = [ os.path.basename(r) for r in glob.glob(DATA_DIR + '/1*') ]
        for run in runs:

            run_info = self.use_run(run, copy=False)
            #print("%s: %s" % (run, run_info.get_status()) )

            # If copy=True you can safely change files in self.run_dir.
            run_info_new = self.use_run(run, copy=True)

            #TODO: make some changes in run_info_new that should not impact
            #the status.

            self.assertEqual(run_info.get_status(), run_info_new.get_status())

    def md(self, fp):
        os.makedirs(os.path.join(self.run_dir, self.current_run, fp))

    def touch(self, fp, content="meh"):
        with open(os.path.join(self.run_dir, self.current_run, fp), 'w') as fh:
            print(content, file=fh)

    def rm(self, dp):
        # Careful with this one...
        rmtree(os.path.join(self.run_dir, self.current_run, dp))

def dictify(s):
    """ Very very dirty minimal YAML parser is OK for testing.
    """
    return dict(zip(s.split()[0::2], s.split()[1::2]))

if __name__ == '__main__':
    unittest.main()

