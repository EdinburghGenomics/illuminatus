#!/usr/bin/env python3

"""
    “Fixes” the output of bcl2fastq to meet our requirements - mostly regarding file names
"""
import os, sys, glob, re

def main():
    """ Usage BCL2FASTQPreprocessor.py <run_dir> <prefix>
    """
    demux_folder_destination = sys.argv[1]
    prefix = sys.argv[2]

    new_filenames_folder_destination = os.path.join( demux_folder_destination , "fixed_filenames/" )

    demux_folder_content = glob.glob( os.path.join( demux_folder_destination , "?????/*/*" ) )

    for fastq_file in demux_folder_content:

        project = os.path.basename ( os.path.split ( os.path.split(fastq_file)[0] )[0] ) # something like: 10528
        library = os.path.basename ( os.path.split(fastq_file)[0] ) # something like: 10528EJ0019L01
        filename = os.path.split(fastq_file)[1] # something like: 10528EJpool03_S19_L005_R1_001.fastq.gz

        # get information from the filename
        matchFilename = re.match( r'(.*)_(.*)_(.*)_(.*)_(.*).fastq.gz', filename, re.M|re.I)

        if not matchFilename:
            next
        pool = matchFilename.group(1) # e.g.: 10528EJpool03
        lane = matchFilename.group(3) # e.g.: L005
        readnumber = matchFilename.group(4) # e.g.: R1

        new_filename_basename = prefix + "_" + lane + "_" + library + "_" + readnumber + ".fastq.gz"

        new_filename_absolute = os.path.join ( new_filenames_folder_destination , project , new_filename_basename )

        print ( fastq_file + " -> " + new_filename_absolute )

    demux_folder_undetermined_fastq = glob.glob( os.path.join( demux_folder_destination , "Undetermined*fastq.gz" ) )

    for undet_fastq_file in demux_folder_undetermined_fastq:
        new_filename_absolute = os.path.join ( new_filenames_folder_destination , os.path.basename( undet_fastq_file ) )

        print ( undet_fastq_file  + " -> " + new_filename_absolute )


if __name__ == '__main__':
    main()
