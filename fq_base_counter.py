#!/usr/bin/env python3

import os, sys, re
import gzip
import json
import itertools, collections
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

""" This tool counts up the reads and bases in a FASTQ file.
    The idea is that for each .fastq.gz, as well as the .md5 file we also
    want a .fasq.gz.counts which has:

     total_reads: ...
     read_length: ...
     total_bases: ...
     non_n_bases: ...
     index_seq: ...

    The script takes a .fastq.gz file to examine. If a -j JSON is supplied
    then the same info will will be extracted from this file instead.

    The index_seq can only be inferred. I'll use the same logic as found
    in qc_tools_python/lib/qc_utils/profile_fq.py
"""

def parse_args():

    description = "Output base counts on a FASTQ file."

    parser = ArgumentParser( description = description,
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("infile", nargs='+',
                        help=".fastq.gz file to be read")
    parser.add_argument("-j", "--json",
                        help="Get info from Stats.json, not from the actual file.")

    return parser.parse_args()

def main(args):

    if args.json:
        with open(args.json) as jfh:
            json_info = json.loads(jfh.read())
        for fn in args.infile:
            print_info(json_to_info(fn, json_info), fn=os.path.basename(fn))

    else:
        for fn in args.infile:
            print_info(scan_fq(fn), fn=os.path.basename(fn))

def scan_fq(filename):
    """ Read a file. The file must actually be a gzipped file, unless it's completely empty,
        which is useful for testing.
    """
    lens_found = collections.Counter()
    bcs_found = collections.Counter()
    ns_found = 0
    bad_barcode = re.compile(br'[N0-9]')

    if os.stat(filename).st_size == 0:
        return dict( total_reads = 0,
                     min_read_len = 0,
                     max_read_len = 0,
                     n_bases = 0       )

    try:
        with gzip.open(filename, mode='rb') as fh:
            for n, l in enumerate(fh):
                #Extract barcode
                if n % 4 == 0:
                    candidate_bc = l.split(b":")[-1].rstrip()

                    if ( len(candidate_bc) < 3 or
                         re.search(bad_barcode, candidate_bc) ):
                        #That's no barcode!
                        pass
                    else:
                        bcs_found[candidate_bc] += 1
                elif n % 4 == 1:
                    lens_found[len(l) - 1] += 1
                    ns_found += l.count(b'N')
    except OSError as e:
        #The GZip module doesn't tell you what file it was trying to read
        e.filename = filename
        e.strerror = e.args[0]
        raise

    return dict( total_reads = (n + 1) // 4,
                 min_read_len = min(lens_found.keys()),
                 max_read_len = max(lens_found.keys()),
                 n_bases = ns_found,
                 bcs_found = bcs_found )

def json_to_info(filename, json_info):
    """ Read the relevant info from json_info, using the filename to infer
        which sample+read we are dealing with.
    """
    fn_bits = os.path.basename(filename).split('.')[0].split('_')

    read = fn_bits[-1]
    lib = fn_bits[-2]
    lane = fn_bits[-3]
    runid = "_".join(fn_bits[0:4])

    # Check the run id matches
    assert json_info['RunId'] == runid, \
        "The JSON file is for run {} but the input file is for run {}.".format(json_info['RunId'], runid)

    # Find the info for this lib
    try:
        laneinfo, = [ l for l in json_info['ConversionResults'] if str(l['LaneNumber']) == lane ]
    except ValueError:
        raise Exception("The JSON file does not contain info about lane {}.".format(lane))

    # Special case for 'unassigned'
    if lib == 'unassigned':
        dres = laneinfo['Undetermined']
    else:
        try:
            dres, = [ d for d in laneinfo['DemuxResults'] if d['SampleId'].endswith(lib) ]
        except ValueError:
            raise Exception("The JSON file does not contain info about library {}.".format(lib))

    try:
        rmet, = [ r for r in dres['ReadMetrics'] if str(r['ReadNumber']) == read ]
    except ValueError:
        raise Exception("No ReadMetrics for read {}.".format(read))

    try:
        ri, = [ ri for ril in json_info["ReadInfosForLanes"] if str(ril["LaneNumber"]) == lane
                   for ri in ril["ReadInfos"] if str(ri["Number"]) == read and not ri["IsIndexedRead"] ]
    except ValueError:
        raise Exception("The JSON file does not contain read info for read {}, lane {}.".format(read, lane))

    # Now we can start building the info...
    res = dict()

    # Not quite the same as what we get from scanning the file but it will still
    # give an appropriate answer.
    res['bcs_found'] = collections.Counter(
                        { im['IndexSequence'].encode() : im['MismatchCounts']['0']
                          for im in dres.get('IndexMetrics', []) } )

    res['total_reads'] = int(dres['NumberReads'])

    res['min_read_len'] = res['max_read_len'] = int(ri['NumCycles'])

    # Unfortunately the JSON doesn't give us the number of no-calls, just this.
    res['q30_bases'] = rmet['YieldQ30']

    return res

def print_info(fq_info, fn='input.fastq.gz'):
    """ Show what we got.
    """

    print( "filename:    {}".format(fn) )

    print( "total_reads: {}".format(fq_info['total_reads']) )

    if fq_info['min_read_len'] == fq_info['max_read_len']:
        total_bases = fq_info['min_read_len'] * fq_info['total_reads']

        print( "read_length: {}".format(fq_info['min_read_len']) )
    else:
        total_bases = fq_info['total_bases']

        print( "read_length: {}-{}".format(fq_info['min_read_len'], fq_info['max_read_len']) )

    print( "total_bases: {}".format(total_bases) )

    if 'n_bases' in fq_info:
        print( "non_n_bases: {}".format(total_bases - fq_info['n_bases']) )

    if 'q30_bases' in fq_info:
        print( "q30_bases:   {}".format(fq_info['q30_bases']) )

    # Some heuristics on the barcode here. I expect a counter object, but a dict with one
    # value will do.
    bcs_found = fq_info.get('bcs_found', {})

    barcode = 'unknown'
    if len(bcs_found) == 0:
        barcode = 'none'
    elif len(bcs_found) == 1:
        barcode, = [ x.decode() for x in bcs_found.keys() ]
    else:
        common_bcs = bcs_found.most_common(2)
        #If the most common occurs twice as often as the next in line
        #we'll consider it the real one.
        if common_bcs[0][1] >= common_bcs[1][1] * 2:
            barcode =  common_bcs[0][0].decode()

    print( "index_seq:   {}".format(barcode) )

if __name__ == '__main__':
    main(parse_args())
