#!/bin/bash
# vim: ft=python

## This workflow should be run in a fastqdata/run directory to
## produce/update all QC reports and md5sums.

# Contents >>>
#   + Embedded BASH script to bootstrap the workflow
#   + Initialisation and configuration
#   + Helper functions
#   + The rules specific to this workflow
#   + More generic rules

"""true" ### Begin shell script part
set -euo pipefail

source "`dirname $0`"/shell_helper_functions.sh

snakerun_drmaa "$0" "$@"

"exit""" ### End of shell script part

#!/usr/bin/env snakemake
import yaml

# TODO - add tools/versions here
CUTADAPT = "/lustre/software/cutadapt/pipeline_current/bin/cutadapt"
FASTQC   = "/lustre/software/FastQC/pipeline_current/fastqc"
INTEROP  = "/lustre/software/interop/pipeline_current/bin"
MULTIQC  = "multiqc"  # The active Python3 VEnv should provide the correct multiqc.

# Other than that, ensure that scripts in the directory with this Snakefile are
# in the PATH
if ( not os.path.dirname(workflow.snakefile) in os.environ['PATH'] and
     not os.path.dirname(os.path.abspath(workflow.snakefile)) in os.environ['PATH'] ):
     os.environ['PATH'] += ':' + os.path.dirname(workflow.snakefile)

def glob():
    """Regular glob() is useful but it can be improved like so.
    """
    from glob import glob
    return lambda p: sorted( (f.rstrip('/') for f in glob(os.path.expanduser(p))) )
glob = glob()

def split_fq_name(n):
    """Break out components from the name of a a FASTQ file.
        eg. 10749/10749DMpool03/170221_K00166_0183_AHHT3HBBXX_8_10749DM0001L01_1.fastq.gz
        eg. 170221_K00166_0183_AHHT3HBBXX_1_unassigned_1.fastq.gz
    """
    if '/' in n:
        proj, pool, fn = n.split('/')
        rdate, rmach, rnum, rfc, lane, lib, read = fn.split('.')[0].split('_')
        return dict( proj = proj,
                     pool = pool,
                     fn = fn,
                     run = "%s_%s_%s_%s" % (rdate, rmach, rnum, rfc),
                     lane = lane,
                     lib = lib,
                     read = read,
                     unassigned = False )
    else:
        rdate, rmach, rnum, rfc, lane, lib, read = n.split('.')[0].split('_')
        return dict( proj = None,
                     pool = None,
                     fn = n,
                     run = "%s_%s_%s_%s" % (rdate, rmach, rnum, rfc),
                     lane = lane,
                     lib = None,
                     read = read,
                     unassigned = (lib == 'unassigned') )

# See what input sequences we are dealing with
all_unassigned_fq = [ f[:-len('.fastq.gz')] for f in glob('*_unassigned_?.fastq.gz') ]
all_assigned_fq   = [ f[:-len('.fastq.gz')] for f in glob('[1-9]*/*/*.fastq.gz') ]
all_fq = (all_assigned_fq + all_unassigned_fq)
all_1_fq = [ fq for fq in all_fq if split_fq_name(fq)['read'] == '1' ]

# There should only be one run, but having runs_and_lanes as a set of pairs is how
# I've done things elsewhere so I may as well stick with it.
runs_and_lanes = sorted(set( (sf['run'], sf['lane']) for f in all_fq for sf in [split_fq_name(f)] ))
runs = sorted(set( rl[0] for rl in runs_and_lanes ))

# === Driver rules ===

rule md5_main:
    input:
        md5      = expand( 'md5sums/{fq}.fastq.gz.md5', fq=all_fq ),

rule qc_main:
    input:
        cutadapt = expand( 'QC/{fq}.cutadapt_out',      fq=all_1_fq ),
        fastqc   = expand( 'QC/{fq}.fastqc.zip',        fq=all_fq )

# Interop files in eg. /lustre/seqdata/170627_D00261_0417_ACAU93ANXX/InterOp/
# The location needs to be passed explicitly via --config interop=..., leaving off
# the final directory name.
rule interop_main:
    input:
        plots = expand( "QC/interop/{run}.{plot}.interop_plot",
                        run = runs,
                        plot = ['qscore_heatmap', 'by_cycle', 'by_lane' ] )
        # and also? Are there per-lane plots to make?

rule demux_stats_main:
    # TODO - gather stats from the bcl2fastq logs etc. Calculate barcode balance, ...
    # This also tries to get the well dups value, if appropriate
    input:
        stats = expand("QC/{rl[0]}_{rl[1]}.stats.yml", rl=runs_and_lanes),
        dups  = expand("QC/{rl[0]}_{rl[1]}.welldups",  rl=runs_and_lanes)

rule metadata_main:
    # TODO - assemble the metadata items for the run. Query the LIMS if necessary.
    input: expand("QC/run_info.{r}.yml", r=runs)

rule multiqc_main:
    output: "QC/multiqc_report.html"
    input:
        config = "QC/multiqc_config.yml",
        meta = rules.metadata_main.input
    shell:
        """which {MULTIQC} >&2
           {MULTIQC} -t edgen -f QC
           rm -rf `dirname {output}`/multiqc_data
           mv -v -t `dirname {output}` multiqc_data multiqc_report.html
        """

localrules: configure_multiqc
rule configure_multiqc:
    # Emits configuration for MultiQC. This may want to be split out into a separate
    # module but for now...
    output: "QC/multiqc_config.yml"
    run:
        conf = dict( title = 'placeholder',
                     intro_text = False,
                     extra_fn_clean_exts = [
                      dict( type = 'regex',
                            pattern = '_[12]\.(?:san|)fastq' )
                     ],
                     #Why did I add this? Oh, to only see the merged data, not the per run-element data.
                     fn_ignore_paths = [ '*__*/1*' ],
                     #Interactive plots please
                     plots_flat_numseries = 1000,
                     #InterOP at the top
                     top_modules = [ 'edgen_interop' ] )

        with open(output[0], "w") as cfh:
            print(yaml.safe_dump(conf, default_flow_style=False), file=cfh)

# === Actual data-gathering rules ===

# Presumably interop data is under {SEQDATA}/{runid}/InterOp
SEQDATA = config.get('seqdata', os.environ.get('SEQDATA_LOCATION', '.'))

rule interop_qscore_heatmap:
    output: "QC/interop/{runid}.qscore_heatmap.interop_plot"
    shell: "{INTEROP}/plot_qscore_heatmap {SEQDATA}/{wildcards.runid} > {output}"

rule interop_by_cycle:
    output: "QC/interop/{runid}.by_cycle.interop_plot"
    shell: "{INTEROP}/plot_by_cycle {SEQDATA}/{wildcards.runid} > {output}"

rule interop_by_lane:
    output: "QC/interop/{runid}.by_lane.interop_plot"
    shell: "{INTEROP}/plot_by_lane {SEQDATA}/{wildcards.runid} > {output}"

# md5summer that keeps the file path out of the .md5 file
rule md5sum_file:
    output: "md5sums/{foo}.md5"
    input: "{foo}"
    shell: "( cd `dirname {input}` && md5sum `basename {input}` ) > {output}"

# cutadapt used only for adapter dimer detection on read 1
rule cutadapt_scan:
    output: "QC/{fq}.cutadapt_out"
    input: "{fq}.fastq.gz"
    params:
        adapters = ["AGATCGGAAGAGC", "CTGTCTCTTATA"]
    shell:
        """{CUTADAPT} -f fastq -O 9 -o /dev/null `for a in {params.adapters} ; do echo -a $a ; done` \
           {input} > {output}
        """

# fastqc runs on single FASTQ files. Apparently this is as it should be.
rule fastqc:
    output: zip = "QC/{foo}.fastq_fastqc.zip",
            html = "{foo}.fastq_fastqc.html"
    input: "{foo}.fastq.gz"
    threads: 2
    shell: "{FASTQC} {input} --outdir `dirname {output.zip}` --noextract --nogroup --threads {threads}"

# meta-data. this can change as the pipeline runs so make the rule depend on the pipeline
# directory
localrules: get_run_metadata
rule get_run_metadata:
    output: "QC/run_info.{runid}.yml"
    input: SEQDATA + "/{runid}/pipeline"
    shell:
        "RunMetaData.py {SEQDATA}/{wildcards.runid} > {output}"

# per-lane infos
WELLDUPS_DATA = config.get('welldups', SEQDATA + '/WellDuplicates')
BCL2FASTQ_OUT = "./demultiplexing"

rule grab_well_dups:
    output: stats = "QC/{runid}_{lane}.welldups"
    run:
        #This only applies to 4000/X runs
        machine_id = wildcards.runid.split('_')[1]
        if machine_id[0] not in ['E', 'K']:
            dup_lines = ['NA']
        else:
            file_to_read = format("{WELLDUPS_DATA}/{wildcards.runid}/*targets_all_lanes.txt")
            try:
                #Snag the well-dups value. With the improved output I can make this less messy.
                wd = slurp_file(file_to_read, glob=True)
                # TODO - grep out the lines and chuck them in the output file
                dup_lines = [ l for l in wd ]
            except Exception:
                dup_lines = ['error reading ' + file_to_read ] 

        #And bung the value into {runid}_{lane}.welldups
        with open(output.stats, 'w') as ofh:
            for l in dup_lines:
                print(l, file=ofh)

rule get_bcl2fastq_stats:
    output: "QC/{runid}_{lane}.stats.yml"
    #input is in /ifs/runqc/ but I can't be sure what the file is called, so just assume it exists
    #also, continue on error - we don't want to crash the whole pipeline just because this fails.
    # FIXME - use value of BCL2FASTQ_LOGS to find the logs.
    shell: "{BCL2FASTQ_STATS} -l {BCL2FASTQ_OUT} {wildcards.runid} {wildcards.lane} > {output} ||" +
           " echo -e 'Run: '\\''{wildcards.runid}'\\''\nLane: '\\''{wildcards.lane}'\\' > {output}"
