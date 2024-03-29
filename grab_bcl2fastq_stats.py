#!/usr/bin/env python3
from __future__ import division, print_function, absolute_import

# FIXME - this should be replaced by stats_json_aggregator.py which is doing the same job but
# in a better way.

# Eg. Try this:
# $ cd /lustre/fastqdata/<anyrun>
# $ grab_bcl2fastq_stats.py demultiplexing/lane1 180119_M01145_0008_000000000-B8RR9 1
# $ stats_json_aggregator.py demultiplexing/lane1/Stats/Stats.json

import os, sys
from glob import glob
import yaml, yamlloader

from collections import OrderedDict
from illuminatus.Formatters import rat

#I guess I want pstdev since I'm calculating variance over the whole run?
#Nope, to be compatible with Illumina we want regular sample stdev
#Note this requires Py3.4 or else the statistics package to be installed via Pip
from statistics import stdev, pstdev, mean


def slurp(filename):
    """Grab a file as a list of strings.
    """
    res = []
    with open(filename) as fh:
        for line in fh:
            res.append(line.rstrip("\n"))
    return res

# Here is some logic which is specific to our drive layout.
def find_fastq_stats(basedir, lane):

    #There might be two stats files.  One for Read1 and one for for the complete read.
#    demux_stats, = ( f for f in
#                    glob('/ifs/runqc/{}/*/Stats/DemuxSummaryF1L{}.txt'.format(runid, lane))
#                    if ('_Read1/' not in f) )

    fastq_stats = [ f for f in
                    glob('{}/Stats/FastqSummaryF1L{}.txt'.format(basedir, lane))
                    if ('_Read1/' not in f) ]

    if len(fastq_stats) == 0:
        return None
    else:
        #This can happen if there were multiple index lengths in a single lane.
        #There is no good solution because both stats files will show a high level of
        #unassigned barcodes.
        #If you want, rename one of the .txt files and then the other will be used.
        assert len(fastq_stats) == 1, "multiple fastq_stats found: %s" % repr(fastq_stats)

        return fastq_stats[0]

def get_data_container():
    #Now, what do we actually want to save out?

    # total assigned reads raw
    # total assigned reads pf
    # total unassigned reads raw
    # total unassigned reads pf

    # assert $1 == $2

    # $2 + $4 / $1 + $3 is the pass rate.  But can we do better?

    # total reads per sample

    # how to calculate the barcode balance?  Standard deviation of reads per sample??
    # Apparently we want the coefficient of variance which is the std deviation / mean
    # or so Donald says, so blame him if it's wrong.

    return OrderedDict.fromkeys([
        "Number of Indexes",
        "Assigned Reads Raw",
        "Unassigned Reads Raw",
        "Assigned Reads PF",
        "Unassigned Reads PF",
        "Fraction PF",
        "Fraction Assigned",
        "Fraction Assigned Raw",
        "Mean Reads Per Sample",
        "Barcode Balance",
    ])

def gather_fastq_stats(fastq_stats_file):

    if fastq_stats_file is None:
        return None

    dc = get_data_container()

    dc['Assigned Reads Raw']   = 0
    dc['Assigned Reads PF']    = 0
    dc['Unassigned Reads Raw'] = 0
    dc['Unassigned Reads PF']  = 0

    # Don't use a defaultdict as we can't dump these as YAML
    reads_per_sample = dict()

    fastq_stats_header = 'SampleNumber Tile NumberOfReadsRaw NumberOfReadsPF'.split()
    for num, line in enumerate(slurp(fastq_stats_file)):

        if num == 0:
            assert line.split() == fastq_stats_header
        else:
            sample_num, tile, rr, rpf = line.split()

            if sample_num == '0':
                dc['Unassigned Reads Raw'] += int(rr)
                dc['Unassigned Reads PF'] += int(rpf)
            else:
                dc['Assigned Reads Raw'] += int(rr)
                dc['Assigned Reads PF'] += int(rpf)

                reads_per_sample.setdefault(sample_num, 0)
                reads_per_sample[sample_num] += int(rpf)

    total_reads_raw = dc['Assigned Reads Raw'] + dc['Unassigned Reads Raw']

    #If it didn't pass the filter, it wasn't assigned, right?
    #Apparently this only applies to 4000 and X runs!
    if dc['Assigned Reads Raw'] != dc['Assigned Reads PF']:
        dc['Fraction Assigned Raw'] = rat((dc['Assigned Reads Raw']), total_reads_raw)

    dc['Fraction PF'] = rat((dc['Assigned Reads PF'] + dc['Unassigned Reads PF']), total_reads_raw )
    dc['Fraction Assigned'] = rat((dc['Assigned Reads PF']), total_reads_raw)

    #Barcode balance... manual calculation of pop std dev
    #Mean Reads Per Sample = Assigned Reads PF / len(reads_per_sample)
    #mean_sq_reads_per_sample = sum( x**2 for x in reads_per_sample.values() ) / len(reads_per_sample)
    #stddev_reads_per_sample = (mean_sq_reads_per_sample - (Mean Reads Per Sample ** 2)) ** 0.5
    #Barcode Balance = stddev_reads_per_sample / Mean Reads Per Sample

    #However, it seems that Illumina use stdev and not pstdev, so I guess we should do the same?
    #Annoyingly I've already done a load of QC with the old values and I can't re-generate
    #them as the logs are gone.

    if reads_per_sample:
        dc['Mean Reads Per Sample'] = mean(reads_per_sample.values())
    else:
        #This shouldn't happen if the sample sheet is valid!
        dc['Mean Reads Per Sample'] = 0

    if len(reads_per_sample) <= 1:
        #With only one barcode in the lane the calculation is meaningless
        dc['Barcode Balance'] = 'NA'
    else:
        dc['Barcode Balance'] = rat(stdev(reads_per_sample.values()), dc['Mean Reads Per Sample'])

    dc['Number of Indexes'] = len(reads_per_sample)

    return dc

def print_fastq_stats(runid, lane, dc, fh=sys.stdout):
    """Print out the data container to a file.  As YAML, of course.
    """

    od = OrderedDict()
    od['Run'] = runid
    od['Lane'] = lane

    #dc can be None if file not found.  Originally missing data would cause the
    #script to error, but I don't want Rapid QC to crash out just for this.
    if dc:
        od.update(dc)

    print(yaml.dump(od,
                    Dumper = yamlloader.ordereddict.CSafeDumper,
                    default_flow_style = False),
          file = fh,
          end = '')

def dump_lane(basedir, runid, lane):
    #Find the stats file, extract the data and print it out.
    print_fastq_stats(runid, lane, gather_fastq_stats(find_fastq_stats(basedir, lane)))

def main():
    """We need to give it a run id and lane to work on.
    """
    if not len(sys.argv) == 4:
        exit("Please specify a base dir, run and lane to examine")
    else:
        dump_lane(*sys.argv[1:])

if __name__ == '__main__':
    main()
