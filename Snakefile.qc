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

# $PATH doesn't get passed to worker nodes on SLURM but I only need it
# for local rules.
export PATH="${PATH}:$(dirname "$0")"

snakerun_drmaa "$0" "$@"

"exit""" ### End of shell script part

#!/usr/bin/env snakemake
import yaml

# TODO - add tools/versions here
CUTADAPT = "/lustre/software/cutadapt/pipeline_current/bin/cutadapt"
FASTQC   = "/lustre/software/FastQC/pipeline_current/fastqc"
INTEROP  = "/lustre/software/interop/pipeline_current/bin"
# The active Python3 VEnv should provide the correct multiqc,
# but multiqc needs to be able to find a working gnuplot.
MULTIQC  = 'env PATH="$PATH:/lustre/software/bin" multiqc'

BCL2FASTQ_STATS = "grab_bcl2fastq_stats.py"

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
                     fname = n,
                     bname = fn.split('.')[0],
                     run = "%s_%s_%s_%s" % (rdate, rmach, rnum, rfc),
                     lane = lane,
                     lib = lib,
                     read = read,
                     unassigned = False )
    else:
        rdate, rmach, rnum, rfc, lane, lib, read = n.split('.')[0].split('_')
        return dict( proj = None,
                     pool = None,
                     fname = n,
                     bname = n.split('.')[0],
                     run = "%s_%s_%s_%s" % (rdate, rmach, rnum, rfc),
                     lane = lane,
                     lib = None,
                     read = read,
                     unassigned = (lib == 'unassigned') )

# See what input sequences we are dealing with
all_unassigned_fq = [ split_fq_name(f) for f in glob('*_unassigned_?.fastq.gz') ]
all_assigned_fq   = [ split_fq_name(f) for f in glob('[1-9]*/*/*.fastq.gz') ]
all_fq = (all_assigned_fq + all_unassigned_fq)
all_1_fq = [ fq for fq in all_fq if fq['read'] == '1' ]

# There should only be one run, but having runs_and_lanes as a set of pairs is how
# I've done things elsewhere so I may as well stick with it.
# On second thoughts - if this script were used on more than one run it would combine
# lanes across runs, so let's forbid it and keep things simple.
runs = set( sf['run'] for sf in all_fq )
assert len(runs) == 1, "Expected to find exactly one run but saw: {}".format(runs)
run, = runs ; del(runs)
lanes = sorted( set( sf['lane'] for sf in all_fq ) )

# === Driver rules ===
rule md5_main:
    input:
        md5      = expand( 'md5sums/{fq[fname]}.md5', fq=all_fq ),

rule qc_main:
    input:
        cutadapt = expand( 'QC/lane{fq[lane]}/{fq[bname]}.cutadapt_out', fq=all_1_fq ),
        fastqc   = expand( 'QC/lane{fq[lane]}/{fq[bname]}_fastqc.zip',   fq=all_fq )

# Interop files in eg. /lustre/seqdata/170627_D00261_0417_ACAU93ANXX/InterOp/
# The location will be inferred from SEQDATA/{runid}/InterOp
rule interop_main:
    input:
        plots = expand( "QC/interop/{run}.{plot}.interop_plot",
                        run = [run],
                        plot = ['qscore_heatmap', 'by_cycle', 'by_lane' ] )
        # and also? Are there per-lane plots to make?

rule demux_stats_main:
    # TODO - gather stats from the bcl2fastq logs etc. Calculate barcode balance, ...
    # This also tries to get the well dups value, if appropriate
    # Also we have the new Stats.json to compete with our stats.yml. A little confusing -
    # do we need both?
    input:
        stats = expand("QC/lane{l}/{r}_{l}.stats.yml", l=lanes, r=[run]),
        dups  = expand("QC/lane{l}/{r}_{l}.welldups",  l=lanes, r=[run]),
        json  = expand("QC/lane{l}/Stats.json",                l=lanes),

rule metadata_main:
    # TODO - assemble the metadata items for the run. Query the LIMS if necessary.
    input: "QC/run_info.{r}.yml".format(r=run)

# For now run this locally. Might want to shift it to the cluster if login-0 gets too
# busy.
# Note this rule does not trigger qc_main etc. so you have to run those explicitly first.
localrules: multiqc_main, run_multiqc
rule multiqc_main:
    input: expand("QC/multiqc_report_lane{l}.html", l=lanes)

rule run_multiqc:
    output:
        report = "QC/multiqc_report_lane{l}.html",
        data = "QC/multiqc_report_lane{l}_data"
    input:
        config = "QC/multiqc_config.yml",
        meta = rules.metadata_main.input
    shell:
        """echo "multiqc is `which multiqc`" >&2
           rm -rf {output.data}
           ln -srf {input.meta} QC/lane{wildcards.l}/
           {MULTIQC} -t edgen -o QC -n `basename {output.report}` -c {input.config} QC/lane{wildcards.l}
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
                            pattern = '_[12]\.(?:san|)fastq$' ),
                      dict( type = 'regex',
                            pattern = '^{}(_._| - )'.format(run) ),
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
    output: "QC/lane{l}/{fq}.cutadapt_out"
    input: "{fq}.fastq.gz"
    params:
        adapters = ["AGATCGGAAGAGC", "CTGTCTCTTATA"]
    shell:
        """{CUTADAPT} -f fastq -O 9 -o /dev/null `for a in {params.adapters} ; do echo -a $a ; done` \
           {input} > {output}
        """

# fastqc runs on single FASTQ files, not read pairs. Apparently this is as it should be.
rule fastqc:
    output: zip = "QC/lane{l}/{fq}_fastqc.zip",
            html = "QC/lane{l}/{fq}_fastqc.html"
    input: "{fq}.fastq.gz"
    threads: 2
    shell: "{FASTQC} {input} --outdir `dirname {output.zip}` --noextract --nogroup --threads {threads}"

# meta-data. this can change as the pipeline runs so make the rule depend on the pipeline
# directory. Also there is only one metadata file per run, not per lane, but it will be
# symlinked by multiqc_main to be picked up on all runs
localrules: get_run_metadata
rule get_run_metadata:
    output: "QC/run_info.{runid}.yml"
    input: SEQDATA + "/{runid}/pipeline"
    shell:
        "RunMetaData.py {SEQDATA}/{wildcards.runid} > {output}"

# per-lane infos
WELLDUPS_DATA = config.get('welldups', SEQDATA + '/WellDuplicates')
BCL2FASTQ_OUT = "demultiplexing"

localrules: grab_well_dups
rule grab_well_dups:
    output: stats = "QC/lane{lane}/{runid}_{lane}.welldups"
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
    # This rule can hopefully be replaced by the direct examination of the .json
    # file by the new module for MultiQC.
    # Logic is a little contorted as I copied the script from the old pipeline
    # where it scanned for the input file.
    output: "QC/lane{lane}/{runid}_{lane}.stats.yml"
    input: BCL2FASTQ_OUT + "/lane{lane}/Stats/FastqSummaryF1L{lane}.txt"
    shell: "{BCL2FASTQ_STATS} {BCL2FASTQ_OUT}/lane{wildcards.lane} {wildcards.runid} {wildcards.lane} > {output}"

localrules: get_bcl2fastq_json
rule get_bcl2fastq_json:
    # Straight up just copies the file into place
    output: "QC/lane{lane}/Stats.json"
    input: BCL2FASTQ_OUT + "/lane{lane}/Stats/Stats.json"
    shell: "cp {input} {output}"
