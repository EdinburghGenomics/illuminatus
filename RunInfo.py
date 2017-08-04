#!/usr/bin/env python3
import os.path
from glob import glob
import sys

from illuminatus.RunInfoXMLParser import RunInfoXMLParser

class RunInfo:
    """This Class provides information about a sequencing run, given a run folder.
       It will parse information from the following sources:
         RunInfo.xml file - to obtain LaneCount
         Run directory content (including pipeline subdir) - to obtain status information
    """
    def __init__( self , run_folder , run_path = '' ):

        # here the RunInfo.xml is parsed into an object
        self.run_path_folder = os.path.join( run_path , run_folder )
        runinfo_xml_location = os.path.join( self.run_path_folder , 'RunInfo.xml' )
        try:
            self.runinfo_xml = RunInfoXMLParser( runinfo_xml_location )
        except Exception:
            #if we can't read it we can't get much info
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

    def _is_read_finished( self, readnum):
        # Will check for existence of Basecalling_Netcopy_complete_ReadX.txt or RTAReadXComplete.txt with X being the provided readnumber
        ReadLOCATION_oldMachines = os.path.join( self.run_path_folder , 'Basecalling_Netcopy_complete_Read'+str(readnum)+'.txt' ) #for miseq and hiseq2500
        ReadLOCATION_newMachines = os.path.join( self.run_path_folder , 'RTARead'+str(readnum)+'Complete.txt' ) #for hiseq4000 and X
        return os.path.exists( ReadLOCATION_oldMachines or ReadLOCATION_oldMachines )

    def _is_new_run( self ):
        # if the pipeline has not yet seen this run before.
        # the pipeline/ folder should not exist
        PIPELINE_FOLDER_LOCATION = os.path.join( self.run_path_folder , 'pipeline' )

        return not os.path.exists( PIPELINE_FOLDER_LOCATION )

    def _was_restarted( self ):
        # returns True if any of the lanes was marked for redo
        RESTARTED_FILE_LOCATION = os.path.join( self.run_path_folder , 'pipeline', 'lane?.redo' )
        redo_files = glob( RESTARTED_FILE_LOCATION )

        return len(redo_files) > 0

    def _was_started( self ):
        """ returns True if ANY of the lanes was marked as started [demultiplexing]
        """
        STARTED_FILE_LOCATION = os.path.join( self.run_path_folder , 'pipeline', 'lane?.started' )
        started_files = glob( STARTED_FILE_LOCATION )

        return len(started_files) > 0

    def _was_finished( self ):
        """ returns True if ALL lanes were marked as done [demultiplexing]
            by comparing number of lanes with the number of lane?.done files
        """
        number_of_lanes = int( self.runinfo_xml.run_info[ 'LaneCount' ] )
        DONE_FILE_LOCATION = os.path.join( self.run_path_folder , 'pipeline', 'lane?.done' )
        finished_files = glob( DONE_FILE_LOCATION )

        return len(finished_files) == number_of_lanes

    def _qc_started( self ):
        return bool(glob( os.path.join(self.run_path_folder, 'pipeline/qc.started') ))

    def _qc_done( self ):
        return bool(glob( os.path.join(self.run_path_folder, 'pipeline/qc.done') ))

    def _was_aborted( self ):
        """ if the processing was aborted, we have a single flag for the whole run
        """
        return os.path.exists( os.path.join( self.run_path_folder , 'pipeline/aborted' ) )

    def _was_failed( self ):
        """ if the processing failed, we have a single flag for the whole run
        """
        # I think it also makes sense to have a single failed flag, but note that any
        # lanes with status .done are still to be regarded as good. Ie. the interpretation
        # of this flag is that any 'started' lane is reallY a 'failed' lane.
        return os.path.exists( os.path.join( self.run_path_folder , 'pipeline/failed' ) )

    def _was_ended( self ):
        """ processing finished due to successful exit, or a failure, or was aborted
        """
        return self._was_finished() or self._was_aborted() or self._was_failed()

    def get_machine_status( self ):
        # workout the status of a sequencer by checking the existence of various touchfiles found in the run folder.
        # possible values are:
        # RUN IS 'complete':
        if self._is_sequencing_finished():
            return "complete"
        if self._is_read_finished(4):
            return "read4complete"
        if self._is_read_finished(3):
            return "read3complete"
        if self._is_read_finished(2):
            return "read2complete"
        if self._is_read_finished(1):
            return "read1complete"
        return False



    def get_status( self ):
        # workout the status of a run by checking the existence of various touchfiles found in the run folder.
        # possible values are:
        # sequencing, new, read1_finished, reads_finished, in_pipeline, complete, failed, redo
        # FIXME - I think we need to differentiate between run status and pipeline status here.

        # RUN IS 'new': if no pipeline/ folder have yet been created.
        if self._is_new_run():
            return "new"

        # this status needs to be dependent on the well_duplicates, otherwise it will only have a short window of execution between read1 and read2
        # which file marks the completeion of welldups???
        if self._is_read_finished(1) and not self._is_read_finished(2):
            return "read1trigger"

        if self._is_read_finished(1) and (self._is_read_finished(2) or self._is_sequencing_finished):
            return "read1complete"

        # RUN IS 'waiting_for_data': if machine_status isn't available yet (how will we distinguish aborted/failed sequencing?)
        if not self.get_machine_status():
            return "waiting_for_data"

        # RUN IS 'redo' if the run is marked for restarting and is ready for restarting (not running):
        if self._is_sequencing_finished() and self._was_restarted() and self._was_ended():
            return "redo"

        # RUN is 'failed' or 'aborted' if flagged as such. There should be no process running.
        if self._was_failed():
            return "failed"
        if self._was_aborted():
            return "aborted"

        # RUN IS 'reads_unfinished'
        if not self._is_sequencing_finished():
            #Double-check that there is no pipeline activity - the run is either still on the sequencer
            #or has been aborted.
            if not ( self._was_started() or self._was_ended() ):
                return "reads_unfinished"

        # FIXME - detect and deal with read1 complete

        # RUN IS 'reads_finished': if RTAComplete.txt is present and the demultiplexing has not started e.g. pipeline/lane?.started files do not exist
        if self._is_sequencing_finished() and not self._was_started() and not self._was_ended():
            return "reads_finished"

        # RUN IS 'in_demultiplexing':
        if self._is_sequencing_finished() and self._was_started() and not self._was_ended():
            return "in_demultiplexing"

        # RUN is 'in_qc':
        if self._is_sequencing_finished() and self._was_finished():
            if self._qc_started():
                return "in_qc"
            elif not self._qc_done():
                return "demultiplexed"

        # RUN IS 'complete':
        if self._is_sequencing_finished() and self._qc_done() and not self._was_restarted():
            return "complete"

        return "unknown"

    def get_yaml(self):
        try:
            out = ( 'RunID: {i[RunId]}\n' +
                    'LaneCount: {i[LaneCount]}\n' +
                    'Instrument: {i[Instrument]}\n' +
                    'Flowcell: {i[Flowcell]}\n' +
                    'Status: {s}\n' +
                    'MachineStatus: {t}').format( i=self.runinfo_xml.run_info, s=self.get_status(), t=self.get_machine_status() )
        except AttributeError: # possible that the provided run folder was not a valid run folder e.g. did not contain a RunInfo.xml
            out = ( 'RunID: unknown\n' +
                    'LaneCount: 0\n' +
                    'Instrument: unknown\n' +
                    'Flowcell: unknown\n' +
                    'Status: unknown\n' +
                    'MachineStatus: unknown')
        return out

if __name__ == '__main__':
    #If no run specified, examine the CWD.
    run = sys.argv[1] if len(sys.argv) > 1 else '.'
    run_info = RunInfo(run)
    print ( run_info.get_yaml() )
