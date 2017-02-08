#!/usr/bin/env python3
import os.path
import glob
import sys

from illuminatus.RunInfoXMLParser import RunInfoXMLParser

class RunInfo:
    """This Class provides information about a sequencing run, given a run folder.
       It will parse information from the following sources:
         RunInfo.xml file - to obtain LaneCount
         Run directory content - to obtain status information
    """
    def __init__( self , run_folder , run_path = '' ):

        # here the RunInfo.xml is parsed into an object
        self.run_path_folder = os.path.join( run_path , run_folder )
        runinfo_xml_location = os.path.join( self.run_path_folder , 'RunInfo.xml' )
        if os.path.exists( runinfo_xml_location ):
                self.runinfo_xml = RunInfoXMLParser( runinfo_xml_location )


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
        # So will only check for this file to determine if run is finished or not
        RTACOMPLETE_LOCATION = os.path.join( self.run_path_folder , 'RTAComplete.txt' )
        return os.path.exists( RTACOMPLETE_LOCATION )

    def _is_new_run( self ):
        # if the pipeline has not yet seen this run before.
        # the pipeline/ folder should not exist
        PIPELINE_FOLDER_LOCATION = os.path.join( self.run_path_folder , 'pipeline' )
        return not os.path.exists( PIPELINE_FOLDER_LOCATION )

    def _was_restarted( self ):
        # returns True if any of the lanes was marked for restart
        RESTARTED_FILE_LOCATION = os.path.join( self.run_path_folder , 'pipeline/lane?.redo' )
        redo_files = glob.glob( RESTARTED_FILE_LOCATION )
        if len(redo_files) > 0:
            return True
        return False

    def _was_started( self ):
        # returns True if ANY of the lanes was marked as started
        STARTED_FILE_LOCATION = os.path.join( self.run_path_folder , 'pipeline/lane?.started' )
        started_files = glob.glob( STARTED_FILE_LOCATION )
        if len(started_files) > 0:
            return True
        return False

    def _was_finished( self ):
        # returns True if ALL lanes were marked as done
        # by comparing number of lanes with the number of lane?.done files
        number_of_lanes = int( self.runinfo_xml.run_info[ 'LaneCount' ] )
        DONE_FILE_LOCATION = os.path.join( self.run_path_folder , 'pipeline/lane?.done' )
        finished_files = glob.glob( DONE_FILE_LOCATION )
        if len(finished_files) == number_of_lanes:
            return True
        return False

    def get_status( self ):
        # workout the status of a run by checking the existence of various touchfiles found in the run folder.
        # possible values are:
        # sequencing, new, read1_finished, reads_finished, in_pipeline, complete, failed, redo

        # RUN IS 'new': if no pipeline/ folder have yet been created.
        if self._is_new_run():
            return "new"

        # RUN IS 'reads_unfinished'
        if not self._is_sequencing_finished() and not self._is_new_run():
            #Double-check that there is no pipeline activity - the run is either still on the sequencer
            #or has been aborted.
            if not ( self._was_started() or self._was_finished() ):
                return "reads_unfinished"

        # RUN IS 'reads_finished': if RTAComplete.txt is present and the demultiplexing has not started e.g. pipeline/lane?.started files do not exist
        if self._is_sequencing_finished() and not self._was_started() and not self._was_finished() and not self._is_new_run():
            return "reads_finished"

        # RUN IS 'in_pipeline':
        if self._is_sequencing_finished() and self._was_started() and not self._was_finished():
            return "in_pipeline"

        # RUN IS 'complete':
        if self._is_sequencing_finished() and self._was_finished() and not self._was_restarted():
            return "complete"

        # RUN IS 'failed':
                #if self._is_sequencing_finished() and not self._is_in_pipeline() and self._is_pipeline_finished():
                #        return "failed"

        # RUN IS 'redo':
        if self._is_sequencing_finished() and self._was_restarted() and self._was_finished():
            return "redo"

        return "unknown"

    def get_yaml(self):
        try:
            out =   'RunID: ' + self.runinfo_xml.run_info[ 'RunId' ] + '\n' + \
                'LaneCount: ' + self.runinfo_xml.run_info[ 'LaneCount' ] + '\n' + \
                'Instrument: ' + self.runinfo_xml.run_info[ 'Instrument' ] + '\n' + \
                'Flowcell: ' + self.runinfo_xml.run_info[ 'Flowcell' ] + '\n' + \
                'Status: ' +  self.get_status()
        except AttributeError: # possible that the provided run folder was not a valid run folder e.g. did not contain a RunInfo.xml
            out =   'RunID: ' + 'unknown' + '\n' + \
                'LaneCount: ' + '0' + '\n' + \
                'Instrument: ' + 'unknown' + '\n' + \
                'Flowcell: ' + 'unknown' + '\n' + \
                'Status: ' + 'unknown'
        return out

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print ("please provide the run folder as an argument")
        sys.exit(1)
    run = sys.argv[1]
    run_info = RunInfo(run, run_path = '')
    print ( run_info.get_yaml() )
