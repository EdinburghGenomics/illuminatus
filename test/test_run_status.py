#!/usr/bin/env python3

import unittest
import sys, os
import glob
from tempfile import mkdtemp
from shutil import rmtree, copytree
from pprint import pprint
from unittest.mock import patch

# Adding this to sys.path makes the test work if you just run it directly.
with patch('sys.path', new=['.'] + sys.path):
    from RunStatus import RunStatus

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/seqdata_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

class T(unittest.TestCase):

    #Helper functions:
    def use_run(self, run_id, copy=False, make_run_info=True):
        """Inspect a run.
           If copy=True, copies a selected run into a temporary folder first.
           Sets self.current_run to the run id and
           self.run_dir to the temporary run dir, temporary or otherwise.
           Also returns a RunStatus object for you.
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
        #If you want to change files around, do that then make a new RunStatus
        #by copying the line below.
        if make_run_info:
            return RunStatus(os.path.join(self.run_dir, self.current_run))

    def gs(self):
        """ Clear the cache and get the status
        """
        run_info = RunStatus(os.path.join(self.run_dir, self.current_run))
        res = dictify(run_info.get_yaml())['PipelineStatus:']
        if VERBOSE: pprint(run_info._exists_cache)
        return res

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

    def test_redo_on_early_fail( self ):
        """ Normally we want to redo after demultiplexing has run, but we can
            also fail on the initial run of samplesheet_fetch.sh which prevents
            read1 processing at all.
        """
        run_info = self.use_run('160726_K00166_0120_BHCVH2BBXX', copy=True)

        # So the run is failed but still waiting for data
        self.touch('pipeline/failed')
        self.assertEqual(self.gs(), 'reads_unfinished')

        self.touch('pipeline/lane1.redo')
        self.assertEqual(self.gs(), 'reads_unfinished')

        self.touch('RTAComplete.txt')
        self.assertEqual(self.gs(), 'failed')

        # Having the pipeline link finally allows this to redo
        self.md('pipeline/output/seqdata/pipeline')
        self.assertEqual(self.gs(), 'redo')

        # Don't worry about read1 processing. We'll mop this up later.
        self.touch('pipeline/read1.started')
        self.assertEqual(self.gs(), 'redo')
        self.touch('pipeline/read1.done')
        self.assertEqual(self.gs(), 'redo')
        self.rm('pipeline/read1.started')
        self.rm('pipeline/read1.done')

        # If the run was not complete we can't redo
        self.rm('RTAComplete.txt')
        self.assertEqual(self.gs(), 'reads_unfinished')
        self.touch('RTAComplete.txt')

        # If processing is started the failed flag overrides the state but we
        # can't redo as we got in a tizz.
        self.touch('pipeline/lane1.started')
        self.assertEqual(self.gs(), 'failed')

        # If read1 processing had finished we'd be back to redo
        self.touch('pipeline/read1.done')
        self.assertEqual(self.gs(), 'redo')
        self.rm('pipeline/read1.done')

        # But without that or a failure we coonclude we're demultiplexing, except that read1 is not
        # done so we trigger that right away.
        self.rm('pipeline/failed')
        self.assertEqual(self.gs(), 'read1_finished')
        self.touch('pipeline/failed')

        # And after redo flag is cleared and lanes are demultiplexed, we could also be failed
        self.rm('pipeline/lane1.redo')
        self.rm('pipeline/lane1.started')
        self.touch('pipeline/lane1.done')
        self.assertEqual(self.gs(), 'failed')

        # But normally the fail would be cleared, and we still need to trigger
        # read1 processing before we get to QC. Aye?
        self.rm('pipeline/failed')
        self.assertEqual(self.gs(), 'read1_finished')

    def test_messy_redo( self ):
        """ If some lanes fail, then you redo just one and it works, then you redo
            everything. I spotted this as a bug while tinkering with run
            180209_D00261_0449_ACC8FGANXX
        """
        self.use_run('160726_K00166_0120_BHCVH2BBXX', copy=True, make_run_info=False)
        self.touch('pipeline/read1.done')
        self.touch('RTAComplete.txt')

        def no_redo(status):
            """ Check the status AND also check
                that adding a lane1.redo file does not change the status
            """
            self.assertEqual(self.gs(), status)
            self.touch('pipeline/lane1.redo')
            self.assertEqual(self.gs(), status)
            self.rm('pipeline/lane1.redo')

        def yes_redo(status):
            """ Check the status AND also check
                that adding a lane1.redo file does change the status to redo
            """
            self.assertEqual(self.gs(), status)
            self.touch('pipeline/lane1.redo')
            self.assertEqual(self.gs(), 'redo')
            self.rm('pipeline/lane1.redo')

        no_redo('reads_finished')

        # Fail demultiplex...
        for l in '12345678':
            self.touch('pipeline/lane{}.started'.format(l))
        self.touch('pipeline/failed')
        yes_redo('failed')

        # Just redo one lane... currently driver.sh will remove all the .started files
        # and re-demultiplex the selected lane.
        for l in '12345678':
            self.rm('pipeline/lane{}.started'.format(l))
        self.rm('pipeline/failed')
        self.touch('pipeline/lane5.done')
        # Now this is not a happy state because you should have restarted ALL the failed
        # lanes. However the design says that we should proceed to QC and thus get to
        # partially_complete:
        self.assertEqual(self.gs(), 'demultiplexed')

        self.touch('pipeline/qc.done')
        self.assertEqual(self.gs(), 'partially_complete')

        # But what is for sure is that a redo of all lanes should get us into state=redo,
        # whether or not the qc.done file is present...
        for l in '12345678':
            self.touch('pipeline/lane{}.redo'.format(l))
        self.assertEqual(self.gs(), 'redo')

        # Removing qc.done has no bearing
        self.rm('pipeline/qc.done')
        self.assertEqual(self.gs(), 'redo')

    def test_weird(self):
        """This shouldn't happen, but what if a run seems to be in both demultiplexing
           and also still awaiting data? The former concern should take precedence.
           This is more a concern for testing that in the real world.
        """
        run_info = self.use_run('180430_M05898_0007_000000000-BR92R', copy=False, make_run_info=False)

        # So the run allegedly started demultiplexing and failed but (!) is still waiting for data
        self.assertEqual(self.gs(), 'reads_unfinished')

        run_info = self.use_run('160607_D00248_0174_AC9E4KANXX_weird', copy=False, make_run_info=False)

        # This one appears unfinished but also has qc.done. We need to be careful not to send it in an
        # infinite processing loop.
        self.assertEqual(self.gs(), 'complete')

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

        def gy():
            """ Clear the cache and get the status
            """
            run_info._exists_cache = dict()
            return dictify(run_info.get_yaml())

        def no_redo(status):
            """ Check the status AND also check
                that adding a lane1.redo file does not change the status
            """
            self.assertEqual(gy()['PipelineStatus:'], status)
            self.touch('pipeline/lane1.redo')
            self.assertEqual(gy()['PipelineStatus:'], status)
            self.rm('pipeline/lane1.redo')

        def yes_redo(status):
            """ Check the status AND also check
                that adding a lane1.redo file does change the status to redo
            """
            self.assertEqual(gy()['PipelineStatus:'], status)
            self.touch('pipeline/lane1.redo')
            self.assertEqual(gy()['PipelineStatus:'], 'redo')
            self.rm('pipeline/lane1.redo')

        # Check initial state
        self.assertEqual(gy(), expected)

        self.rm('pipeline')

        expected['PipelineStatus:'] = 'new'
        self.assertEqual(gy(), expected)

        # We're basing the read1 trigger on the appearance of data files for the second cycle,
        # (until we change our minds and use the first cycle after the last index read)
        # so for this run we need to fake something for cycle 152.
        self.md('Data/Intensities/BaseCalls/L001/C152.1')
        self.touch('Data/Intensities/BaseCalls/L001/C152.1/foo.bcl')

        # Should still be new until we put the pipeline dir back!
        self.assertEqual(gy()['PipelineStatus:'], 'new')
        self.assertEqual(gy()['MachineStatus:'], 'read1_complete')
        self.md('pipeline')
        no_redo('read1_finished')

        # For this one, let's say that read1 processing completes before the run finishes (as
        # in the normal case)
        self.touch('pipeline/read1.started')
        no_redo('in_read1_qc')

        # And the read1 processing finishes
        self.touch('pipeline/read1.done')
        no_redo('reads_unfinished')

        # Removing read1.started should not matter
        self.rm('pipeline/read1.started')
        no_redo('reads_unfinished')

        # Now we finish the reads
        self.touch('RTAComplete.txt')
        no_redo('reads_finished')
        self.assertEqual(gy()['MachineStatus:'], 'complete')

        # And we start the demultiplexing
        self.touch('pipeline/lane1.started')
        no_redo('in_demultiplexing')

        # And finish it
        for l in '12345678':
            self.touch('pipeline/lane{}.done'.format(l))
        no_redo('in_demultiplexing')

        # Finish it properly!
        self.rm('pipeline/lane1.started')
        yes_redo('demultiplexed')

        # And if we try to redo a lane before QC starts...
        # (actually I just checked this)
        self.touch('pipeline/lane2.redo')
        self.assertEqual(gy()['PipelineStatus:'], 'redo')

    def test_read_states_oops(self):
        """Confusion will happen if all lanes fail the first time but
           you only redo one lane and that works. You might do this for testing,
           I guess, before re-doing the whole thing.
        """
        run_info = self.use_run('160726_K00166_0120_BHCVH2BBXX', copy=True)

        self.touch('RTAComplete.txt')
        self.touch('pipeline/read1.done')
        self.touch('pipeline/qc.done')

        self.assertEqual( dictify(run_info.get_yaml())['PipelineStatus:'], 'partially_complete')


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

        def gy():
            """ Clear the cache and get the status
            """
            run_info._exists_cache = dict()
            res = dictify(run_info.get_yaml())
            if VERBOSE: pprint(run_info._exists_cache)
            return res

        def no_redo(status):
            """ Check the status AND also check
                that adding a lane1.redo file does not change the status
            """
            self.assertEqual(gy()['PipelineStatus:'], status)
            self.touch('pipeline/lane1.redo')
            self.assertEqual(gy()['PipelineStatus:'], status)
            self.rm('pipeline/lane1.redo')

        def yes_redo(status):
            """ Check the status AND also check
                that adding a lane1.redo file does change the status to redo
            """
            self.assertEqual(gy()['PipelineStatus:'], status)
            self.touch('pipeline/lane1.redo')
            self.assertEqual(gy()['PipelineStatus:'], 'redo')
            self.rm('pipeline/lane1.redo')

        self.assertEqual(gy(), expected)

        # Add the pipeline dir
        self.md('pipeline')
        no_redo('reads_unfinished')

        # We're basing the read1 trigger on the appearance of data files for the second cycle,
        # (until we change our minds and use the first cycle after the last index read)
        # so for this run we need to fake something for cycle 27.
        self.md('Data/Intensities/BaseCalls/L001/C27.1')
        self.touch('Data/Intensities/BaseCalls/L001/C27.1/foo.bcl')

        no_redo('read1_finished')

        # Adding an RTAComplete.txt file should not change this status
        self.touch('RTAComplete.txt')
        no_redo('read1_finished')

        # Adding read1.started should push us to the state where ops will trigger in parallel
        self.touch('pipeline/read1.started')
        no_redo('in_read1_qc_reads_finished')

        # A failure at this point should drop us back to 'in_read1_qc'
        self.touch('pipeline/failed')
        no_redo('in_read1_qc')

        # This should make no difference...
        self.touch('pipeline/lane1.started')
        no_redo('in_read1_qc')

        # Then only when the read1 finishes should we be failed
        # And now redo is possible
        self.touch('pipeline/read1.done')
        yes_redo('failed')

        # Clearing the failure and leaving read1.done should get us to reads_finished
        self.rm('pipeline/lane1.started')
        self.rm('pipeline/failed')
        no_redo('reads_finished')

        self.touch('pipeline/lane1.started')
        no_redo('in_demultiplexing')

        self.rm('pipeline/lane1.started')
        self.touch('pipeline/lane1.done')
        yes_redo('demultiplexed')

        # OK, but if the read1.done file never appeared we should still be in in_read1_qc
        self.rm('pipeline/read1.done')
        no_redo('in_read1_qc')

        # And if the read1.started file vanishes we go right back to read1_finished,
        # as QC should not start until both read1 and demultiplexing are done.
        # Though in practise this state should not happen.
        # Redo at this point is not allowed
        self.rm('pipeline/read1.started')
        no_redo('read1_finished')


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
        # Careful with this one, it's basically rm -rf
        try:
            rmtree(os.path.join(self.run_dir, self.current_run, dp))
        except NotADirectoryError:
            os.remove(os.path.join(self.run_dir, self.current_run, dp))

def dictify(s):
    """ Very very dirty minimal YAML parser is OK for testing.
    """
    return dict(zip(s.split()[0::2], s.split()[1::2]))

if __name__ == '__main__':
    unittest.main()

