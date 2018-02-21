#!/usr/bin/env python3
import os.path
from glob import glob
import sys

from illuminatus.RunInfoXMLParser import RunInfoXMLParser, instrument_types

class RunStatus:
    """This Class provides information about a sequencing run, given a run folder.
       It will parse information from the following sources:
         RunInfo.xml file - to obtain LaneCount
         Run directory content (including pipeline subdir) - to obtain status information
    """
    def __init__( self , run_folder , opts = '' ):

        # here the RunInfo.xml is parsed into an object
        self.run_path_folder = run_folder
        # In the case where we're looking at a fastqdata directory, examine the
        # seqdata link
        if os.path.isdir(os.path.join(self.run_path_folder, 'seqdata', 'pipeline')):
            self.run_path_folder = os.path.join(self.run_path_folder, 'seqdata')

        self.quick_mode = 'q' in opts

        runinfo_xml_location = os.path.join( self.run_path_folder , 'RunInfo.xml' )
        self._exists_cache = {}

        self.trigger_cycles = [1]
        self.last_read1_read = 1

        try:
            if self.quick_mode:
                # We only care about instrument (and pipelinestatus)
                self.runinfo_xml = QuickInfo( self.run_path_folder )
            else:
                self.runinfo_xml = RunInfoXMLParser( runinfo_xml_location )

                #Get a list of the first cycle number of each read
                for r, l in sorted(self.runinfo_xml.read_and_length.items()):
                    self.trigger_cycles.append(self.trigger_cycles[-1] + int(l))

                #At some point, we might redefine read1 as ending after the last index read.
                #For now, we have it ending after the actual first read.

                # try:
                #     self.last_read1_read = max( k for k, v in self.runinfo_xml.read_and_indexed.items()
                #                                 where v == 'Y' )
                # except ValueError:
                #     # No index reads. Keep the default value of 1.
                #     pass

        except Exception:
            #if we can't read it we can't get much info
            if os.environ.get('DEBUG', '0') != '0': raise
            self.runinfo_xml = None

    def _is_sequencing_finished( self ):

        # the following type of files exist in a run folder with the number varying depending on the number of reads:
        # Basecalling_Netcopy_complete.txt
        # ImageAnalysis_Netcopy_complete.txt
        # RUN/RTARead1Complete.txt
        # RUN/RTARead3Complete.txt
        # RUN/RTARead2Complete.txt
        # RUN/RTARead4Complete.txt
        # RUN/RTAComplete.txt

        # however there were no runs where the RTAComplete.txt was not the last file written to the run folder.
        # So will only check for this file to determine if sequencing has finished or not
        RTACOMPLETE_LOCATION = os.path.join( self.run_path_folder , 'RTAComplete.txt' )
        return os.path.exists( RTACOMPLETE_LOCATION )

    def _exists( self, glob_pattern ):
        """ Returns if a file exists and caches the result.
            The check will be done with glob() so wildcards can be used, and
            the result will be the number of matches.
        """
        if glob_pattern not in self._exists_cache:
            self._exists_cache[glob_pattern] = len(glob( os.path.join(self.run_path_folder, glob_pattern) ))

        return self._exists_cache[glob_pattern]

    def _is_read_finished( self, readnum ):
        # This used to check for existence of Basecalling_Netcopy_complete_ReadX.txt or RTAReadXComplete.txt with
        # X being the provided readnumber
        # However, the NovaSeq doesn't seem to write any such file and the logic being different per sequencer is
        # confusing, so we're instead looking for the actual data, even though it is possible that out-of-order
        # copying will make this unreliable.
        """
        ReadLOCATION_oldMachines = os.path.join( self.run_path_folder , 'Basecalling_Netcopy_complete_Read'+str(readnum)+'.txt' ) #for miseq and hiseq2500
        ReadLOCATION_newMachines = os.path.join( self.run_path_folder , 'RTARead'+str(readnum)+'Complete.txt' ) #for hiseq4000 and X
        return os.path.exists( ReadLOCATION_oldMachines or ReadLOCATION_oldMachines )
        """
        try:
            cycle = self.trigger_cycles[int(readnum)]
            return self._exists( "Data/Intensities/BaseCalls/L001/C{}.1/*".format(cycle) )
        except Exception:
            return False

    def _is_new_run( self ):
        # if the pipeline has not yet seen this run before.
        # the pipeline/ folder should not exist
        return not self._exists( 'pipeline' )

    def _was_restarted( self ):
        """ returns True if any of the lanes was marked for redo
        """
        return self._exists( 'pipeline/lane?.redo' )

    def _was_started( self ):
        """ returns True if ANY of the lanes was marked as started [demultiplexing]
        """
        return self._exists( 'pipeline/lane?.started' )

    def _read1_triggered( self ):
        """ if read1 processing was started. If it completed, that implies it was started.
        """
        return self._exists( 'pipeline/read1.started' ) or self._exists( 'pipeline/read1.done' )

    def _read1_done( self ):
        return self._exists( 'pipeline/read1.done' )

    def _was_finished( self ):
        """ returns True if ALL lanes were marked as done [demultiplexing]
            by comparing number of lanes with the number of lane?.done files
        """
        number_of_lanes = int( self.runinfo_xml.run_info[ 'LaneCount' ] )

        return self._exists( 'pipeline/lane?.done' ) == number_of_lanes

    def _was_demultiplexed( self ):
        """ In contrast to the above, a run can be partially demultiplexed but ready for
            QC nonetheless.
            So return true if there is at least one .done file and no .started files/
        """
        return self._exists( 'pipeline/lane?.done' ) > 0 and self._exists( 'pipeline/lane?.started' ) == 0

    def _qc_started( self ):
        return self._exists( 'pipeline/qc.started' ) or self._exists( 'pipeline/qc.done' )

    def _qc_done( self ):
        return self._exists( 'pipeline/qc.done' )

    def _was_aborted( self ):
        """ if the processing was aborted, we have a single flag for the whole run
        """
        return self._exists( 'pipeline/aborted' )

    def _was_failed( self ):
        """ if the processing failed, we have a single flag for the whole run
        """
        # I think it also makes sense to have a single failed flag, but note that any
        # lanes with status .done are still to be regarded as good. Ie. the interpretation
        # of this flag is that any 'started' lane is reallY a 'failed' lane.
        return self._exists( 'pipeline/failed' )

    def _was_ended( self ):
        """ processing finished due to successful exit, or a failure, or was aborted
            note that failed runs always need operator intervention, if only to say that
            we will not process them further and flag them aborted
        """
        return self._qc_done() or self._was_aborted() or self._was_failed()

    def get_machine_status( self ):
        """ work out the status of a sequencer by checking the existence of various touchfiles found in the run folder.
        """
        if self.quick_mode:
            return 'not_reported'

        if self._is_sequencing_finished():
            return "complete"
        for n in range(len(self.trigger_cycles), 0 , -1):
            if self._is_read_finished(n):
                return "read{}_complete".format(n)
        return "waiting_for_data"


    def get_status( self ):
        """ Work out the status of a run by checking the existence of various touchfiles
            found in the run folder.
            All possible values are listed in doc/qc_trigger.gv
            Behaviour with the touchfiles in invalid states is undefined, but we'll always
            report a valid status and in general, if in doubt, we'll report a status that
            does not trigger an action.
            ** This logic is convoluted. Before modifying anything, make a test that reflects
               the change you want to see, then after making the change always run the tests.
               Otherwise you will get bitten in the ass!
        """

        # 'new' takes precedence
        if self._is_new_run():
            return "new"

        # RUN IS 'redo' if the run is marked for restarting and is ready for restarting (not running):
        if self._is_sequencing_finished() and self._was_restarted() and (
            self._was_ended() or (self._read1_done() and self._was_demultiplexed() and not self._qc_started()) ):
            return "redo"

        # RUN is 'failed' or 'aborted' if flagged as such. This implies there no processing running, but
        # we can't check this directly. Maybe could add some indirect checks?
        if self._was_aborted():
            # Aborted is a valid end state and takes precedence over 'failed'
            return "aborted"
        if self._was_failed():
            # But we might still be busy processing read 1
            if self._read1_triggered() and not self._read1_done():
                return "in_read1_qc"
            else:
                return "failed"

        # If the run is ended without error we're done, but because of the way the
        # redo mechanism works it's possible for a run to fail then be partially
        # re-done. But that doesn't make it complete.
        if self._was_ended():
            if self._was_finished():
                return "complete"
            else:
                return "partially_complete"

        # If the RUN is 'in_qc' we want to leave it cooking
        if self._qc_started() and (not self._qc_done()):
            return "in_qc"

        # 'read1_finished' status triggers the well dups scanner. We're currently triggering at the end of read 1 but this
        # could change to the last index read, as controlled by the constructor above.
        if self._is_read_finished(self.last_read1_read) or self._is_sequencing_finished():
            if (not self._read1_triggered()):
                # Triggering read1 processign takes precedence
                return "read1_finished"
            elif (not self._read1_done()) and (self._is_sequencing_finished()):
                # Decide if demultiplexing needs to start, or is running, or has finished
                if (self._was_finished()):
                    return "in_read1_qc"
                elif (self._was_started()):
                    return "in_demultiplexing"
                else:
                    return "in_read1_qc_reads_finished"
            elif (not self._read1_done()):
                # well dupes is running and we're still waiting for data to do anything else
                return "in_read1_qc"

        # That should be all the Read1 states out of the way.

        if self._was_demultiplexed():
            return "demultiplexed"
        elif self._was_started():
            return "in_demultiplexing"

        # So that leaves us with a run that's either waiting for reads or is ready
        # for demultiplexing.

        # RUN IS 'reads_unfinished' if we're just waiting for data
        if self._is_sequencing_finished():
            return "reads_finished"
        else:
            return "reads_unfinished"

    def get_yaml(self):
        pstatus = 'unknown'
        try:
            # Check for an 'aborted' file, since we want to recognise aborted runs no matter
            # what else we see.
            if self._was_aborted():
                pstatus = 'aborted'

            out = ( 'RunID: {i[RunId]}\n' +
                    'LaneCount: {i[LaneCount]}\n' +
                    'Instrument: {i[Instrument]}\n' +
                    'Flowcell: {i[Flowcell]}\n' +
                    'PipelineStatus: {s}\n' +
                    'MachineStatus: {t}').format( i=self.runinfo_xml.run_info, s=self.get_status(), t=self.get_machine_status() )
        except Exception: # possible that the provided run folder was not a valid run folder e.g. did not contain a RunInfo.xml
            if os.environ.get('DEBUG', '0') != '0': raise

            out = ( 'RunID: unknown\n' +
                    'LaneCount: 0\n' +
                    'Instrument: unknown\n' +
                    'Flowcell: unknown\n' +
                    'PipelineStatus: {s}\n' +
                    'MachineStatus: unknown').format( s=pstatus )
        return out

class QuickInfo:
    """ Just get the instrument name out of the dir name.
        Involves a little copy/paste from RunInfoXMLParser
        We also need to know the number of lanes, in order to calculate "_was_finished",
        which for now we'll just guess(!)
    """
    def __init__(self, run_dir):

        try:
            runid = os.path.basename(run_dir).split('.')[0]
            instr = runid.split('_')[1]
        except Exception:
            runid = os.path.basename(os.path.dirname(run_dir)).split('.')[0]
            instr = runid.split('_')[1]

        instr0 = instr[0]
        for idmap in instrument_types:
            if instr0 == idmap[0]:
                instr = idmap[2:] + '_' + instr
                break

        # Guess the lane count without reading the XML
        lane_count = 0
        if instr0 in 'M':
            lane_count = 1
        elif instr0 in 'KE':
            lane_count = 8
        elif instr0 in 'D':
            lane_count = 2 if runid.split('_')[3][1] == 'H' else 8
        elif instr0 in 'A':
            # FIXME - this is a wild guess. Also what about the single-lane flowcell?
            lane_count = 2 if runid.split('_')[3][-3] == 'M' else 4

        # Assuming that the run id is the directory name is a little risky but fine for quick mode
        self.run_info = dict( RunId=runid, LaneCount=lane_count, Instrument=instr, Flowcell='not_reported' )

if __name__ == '__main__':
    #Very cursory options parsing
    optind = 1 ; opts = ''
    if sys.argv[optind:] and sys.argv[optind].startswith('-'):
        optind += 1
        opts = sys.argv[optind][1:]

    #If no run specified, examine the CWD.
    runs = sys.argv[optind:] or ['.']
    for run in runs:
        run_info = RunStatus(run, opts)
        print ( run_info.get_yaml() )
