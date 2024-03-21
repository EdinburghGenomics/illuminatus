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
# for local rules to see programs in this directory. Toolbox path is a separate
# thing and will be added explicitly.
export TOOLBOX="$(find_toolbox)"
export PATH="${PATH}:$(dirname "$0")"

snakerun_drmaa "$0" "$@"

"exit""" ### End of shell script part

#!/usr/bin/env snakemake
import yaml, json
from snakemake.utils import format

# $(dirname "$0")/toolbox is the default place for all external deps.
# It should mostly be links (maybe a little wrapper script or two) so if you want to
# test with a new version of anything you can copy the whole directory and set $TOOLBOX in
# your test environment (maybe in environ.sh). Or for tinkering with the code
# in this file you could just temporarily ignore $TOOLBOX, but for deployment this is not
# a good idea.
#
# Tools included within the Illuminatus code or within the active Python3 VEnv
# will already be in the PATH, but they may call out to tools in the TOOLBOX -
# eg. multiqc needs to be able to find a working gnuplot.
# (note that snakerun_drmaa is what currently takes care of activating the VEnv for cluster jobs)
#
# Tools we currently need in the toolbox:
#   cutadapt, fastqc, gnuplot (indirectly),
#   interop_plot_qscore_heatmap, interop_plot_by_cycle, interop_plot_by_lane
# If you want to use a test toolbox, just set the env var. No need to hack this code!
TOOLBOX = 'env PATH="{}:$PATH"'.format(os.environ['TOOLBOX'])

# Other than that, ensure that scripts in the directory with this Snakefile are
# in the PATH (we have to do it here as $PATH does not get preserved on cluster jobs):
#   fq_base_counter.py, summarize_for_overview.py, summarize_post_bcl2fastq.py, summarize_lane_contents.py, stats_json_aggregator.py
if ( not os.path.dirname(workflow.snakefile) in os.environ['PATH'].split(':') and
     not os.path.dirname(os.path.abspath(workflow.snakefile)) in os.environ['PATH'].split(':') ):
     os.environ['PATH'] += ':' + os.path.dirname(workflow.snakefile)

# DEBUG. Note that the TOOLBOX doesn't go in the PATH - you have to invoke it explicitly.
#print("PATH is {}".format(os.environ['PATH']), file=sys.stderr)

def glob():
    """Regular glob() is useful but it can be improved like so.
    """
    from glob import glob
    return lambda p: sorted( (f.rstrip('/') for f in glob(os.path.expanduser(p))) )
glob = glob()

def ifexists(filepattern, single=False):
    """Allows me to have optional inputs. If the file does not exist
       we just run the rule without it.
    """
    gfp = glob(filepattern)
    if len(gfp) > 1 and single:
        raise RuntimeError("{} files match the patern '{}'".format(len(gfp), filepattern))
    return gfp

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
                     fname = n[:-len('.fastq.gz')],
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
                     fname = n[:-len('.fastq.gz')],
                     bname = n.split('.')[0],
                     run = "%s_%s_%s_%s" % (rdate, rmach, rnum, rfc),
                     lane = lane,
                     lib = None,
                     read = read,
                     unassigned = (lib == 'unassigned') )

def get_assigned_fq():
    try:
        with open("projects_ready.txt") as fh:
            all_projects = fh.read().split()
    except FileNotFoundError:
        # Not sure if we want this fallback or not?
        all_projects = ["[1-9]*", "ControlLane"]
    return [ fq for p in all_projects for fq in glob(p + '/*/*.fastq.gz') ]

# See what input sequences we are dealing with (if any, yet)
# I wanted to use a hack to stop this being re-run on every cluster job,
# but it didn't work as Snakemake sometimes re-runs itself even for local jobs.
all_unassigned_fq  = [ split_fq_name(f) for f in glob('*_unassigned_?.fastq.gz') ]
all_unassigned_umi = [ split_fq_name(f) for f in glob('*_unassigned_UMI.fastq.gz') ]
all_unassigned     = ( all_unassigned_fq + all_unassigned_umi )

all_assigned       = [ split_fq_name(f) for f in get_assigned_fq() ]
all_assigned_fq    = [ fq for fq in all_assigned if fq['read'] != 'UMI' ]
all_assigned_umi   = [ fq for fq in all_assigned if fq['read'] == 'UMI' ]

all_fq             = ( all_assigned_fq + all_unassigned_fq )
all_1_fq           = [ fq for fq in all_fq if fq['read'] == '1' ]
all_u1_fq          = [ fq for fq in all_unassigned_fq if fq['read'] == '1' ]

all_all            = ( all_fq + all_unassigned_umi + all_assigned_umi )

if all_all:
    # If there are any fastq files there must be some from read 1.
    assert all_1_fq, "No read1 files found in {}, but there were {} fastq files in total.".format(
                                              os.getcwd(),       len(all_all) )

# There should only be one run. But what is it called?
# If config['runid'] is set we use that, otherwise infer from all_all, otherwise
# the current directory name will do.
try:
    runs = set( sf['run'] for sf in all_all )
    if 'runid' in config: runs.add(config['runid'])
    assert len(runs) <= 1, "Expected to find only one run in {} but saw: {}".format(os.getcwd(), runs)
    RUN, = runs
except ValueError:
    # Revert to using name of CWD
    RUN = os.path.basename(os.path.realpath(os.getcwd()))
finally:
    assert '_' in RUN
    del(runs)

# Since there is a possibility that one or more lanes may fail completely and produce no FASTQ
# I need to look for Stats.json, which always appears.
# FIXME - this empty case is still failing at present since BCL2FASTQPostprocessor.py sees no projects!
all_stats_json_lanes = [ f.split('/')[1][4:] for f in glob("demultiplexing/lane*/Stats/Stats.json") ]
all_bc_check_lanes   = [ f.split('/')[2][4:] for f in glob("QC/bc_check/lane*/") ]
lanes = sorted( set( [sf['lane'] for sf in all_all] + all_stats_json_lanes + all_bc_check_lanes ) )

# All report names - lane1, lane2, ..., overview

# This will not generate the per-lane reports until the demultiplexing has been done.
allreps = expand("lane{l}", l=lanes) + ['overview']

# === Driver rules ===
#...have migrated to the bottom so they can refer to the inputs/outputs of other rules

# === Report-making rules ===

# For now run this locally. Might want to shift it to the cluster if login-0 gets too
# busy, but then the risk is arbitrary delay if the cluster is full up.
# Note this rule does not trigger qc_main etc., because we need to be able to make a
# skeleton report before we have the actual data, so you need to trigger any qc steps
# explicitly. It should be possible to run multicq_main with the -F flag (force full
# re-run) without triggering any cluster jobs, so to that end we can't depend on laneinfo,
# as this potentially triggers the InterOP stuff.
localrules: multiqc_main, run_multiqc
rule multiqc_main:
    input:
        overview = "QC/multiqc_report_overview.html",
        lanereps = expand("QC/multiqc_report_lane{l}.html", l=lanes)

rule run_multiqc:
    output:
        report = "QC/multiqc_report_{l}.html",
        data = directory("QC/multiqc_report_{l}_data")
    input:
        config   = "QC/multiqc_config.yml",
        runinfo  = "QC/run_info.{r}.1.yml".format(r=RUN),
    params:
        pstatus  = config.get('pstatus') or "not specified",
        comment  = [ "-b", config.get('comment') ] if config.get('comment') else []
    shell:
        """echo "multiqc is `which multiqc`" >&2
           rm -rf {output.data}
           mkdir -p  QC/{wildcards.l}
           ln -srf {input.runinfo} QC/{wildcards.l}/
           {TOOLBOX} multiqc -t edgen -o QC -n `basename {output.report}` -c {input.config} {params.comment:q} \
                QC/{wildcards.l} \
                --lane {wildcards.l} --pipeline_status {params.pstatus:q}
        """

localrules: configure_multiqc
rule configure_multiqc:
    # Emits configuration for MultiQC. This may want to be split out into a separate
    # module but for now I'll just embed it here. The config wants to be saved out per run
    # so we can have provenance, so the file currently gets moved over to multiqc_reports/ by
    # upload_report.sh (so if you want to re-run MultiQC manually you need to copy it back!)
    # Strictly, we should have a 'min_multiqc_version' since I'm
    # often adding new possible settings in MultiQC then adding them to this config and they
    # are not backwards-compatible.
    output: "QC/multiqc_config.yml"
    run:
        conf = dict( title = 'placeholder',
                     intro_text = False,
                     # MultiQC should not try to contact the internet in any way...
                     no_version_check = True,
                     extra_fn_clean_exts = [
                      dict( type = 'regex',
                            pattern = '\.(?:san|)fastq$' ),
                      dict( type = 'regex',
                            pattern = '(^|.*/){}_._'.format(RUN) ),
                      dict( type = 'regex',
                            pattern = '.*__' ),
                      dict( type = 'regex',
                            pattern = '_[12]_screen' ),
                      dict( type = 'regex',
                            pattern = '[Uu]ndetermined$',
                            replace = 'unassigned' ),
                     ],
                     define_merge_groups = [
                      dict( name = 'read_pairs',
                            regex = '_([12])$' ),
                     ],
                     # Why did I add this? Oh, to only see the merged data, not the per run-element data.
                     # But it doesn't apply to run reports anyway.
                     fn_ignore_paths = [ '*__*/1*' ],
                     # Interactive plots please
                     plots_flat_numseries = 1000,
                     # No beeswarms
                     max_table_rows = 2000,
                     # Custom content
                     top_modules = [ 'custom_content', 'edgen_interop' ],
                     module_order = [ 'unassigned_barcodes',
                                      'edgen_cutadapt',
                                      'fastqc',
                                      'edgen_fastqc_original',
                                      'fastq_screen',
                                      'bcl2fastq' ],
                     fastqc_config = dict(
                        plots_enabled = [ "sequence_quality_plot",
                                          "per_seq_quality_plot",
                                          #"sequence_content_plot",
                                          "gc_content_plot",
                                          "n_content_plot",
                                          "seq_dup_levels_plot" ] ),
                     fastq_screen_config = dict(
                        tack_on_images = True ),
                     bcl2fastq_config = dict(
                        add_index_sequences = True,
                        add_pool_names = True ),
                     # Karim asked me to try changing this setting, but the default seems OK
                     fastqscreen_simpleplot = 160,
                   )

        with open(str(output), "w") as cfh:
            print(yaml.safe_dump(conf, default_flow_style=False), file=cfh)

# === Actual data-gathering rules ===

# Presumably interop data is under {SEQDATA_LOCATION}/{runid}/InterOp
# But if there is a seqdata symlink, follow that instead.
# And as always, config takes priority over both.
SEQDATA = os.path.realpath('./seqdata')
if not os.path.isdir(SEQDATA) or ('seqdata' in config):
    # Nope, look for a match by name.
    SEQDATA = config.get('seqdata', os.path.join(os.environ.get('SEQDATA_LOCATION', '.'), RUN))

rule interop_qscore_heatmap:
    output: "{foo}/qscore_heatmap.interop_plot"
    input:
        idir = format("{SEQDATA}/InterOp"),
        qmetrics = glob(format("{SEQDATA}/InterOp/QMetricsOut.bin"))
    shell: "{TOOLBOX} interop_plot_qscore_heatmap {input.idir}/.. > {output}"

rule interop_by_cycle:
    output: "{foo}/by_cycle.interop_plot"
    input:
        idir = format("{SEQDATA}/InterOp"),
        qmetrics = glob(format("{SEQDATA}/InterOp/CorrectedIntMetricsOut.bin"))
    shell: "{TOOLBOX} interop_plot_by_cycle {input.idir}/.. > {output}"

# This now uses my custom Python plotter not toolbox/interop_plot_by_lane"
rule interop_by_lane:
    output: "{foo}/by_lane.interop_plot"
    input:
        idir = format("{SEQDATA}/InterOp"),
        qmetrics = glob(format("{SEQDATA}/InterOp/TileMetricsOut.bin"))
    shell: "pf_vs_occupied.py {input.idir}/.. > {output}"

# I thought this was plotting for all cycles but in fact it simply plots for cycle 1
rule interop_flowcell:
    output: "{foo}/flowcell.interop_plot"
    input:
        idir = format("{SEQDATA}/InterOp"),
        tmetrics = glob(format("{SEQDATA}/InterOp/CorrectedIntMetricsOut.bin"))
    shell: "{TOOLBOX} interop_plot_flowcell {input.idir}/.. > {output}"

# This version plots for all cycles. If I want the overall I'll need to calculate it
# myself.
rule interop_flowcell_all:
    output: "{foo}/flowcell_all.interop_plot"
    input:
        idir = format("{SEQDATA}/InterOp"),
        tmetrics = glob(format("{SEQDATA}/InterOp/CorrectedIntMetricsOut.bin"))
    shell:
        # Loop until we get the error: Cycle number exceeds total number of cycles
        # Then assert that the loop ran at least once and the output is not empty.
        """for i in `seq 1000` ; do
             {TOOLBOX} interop_plot_flowcell --filter-by-cycle=$i {input.idir}/.. >> {output} || break
           done
           [ $i -gt 1 ] && [ -s {output} ]
        """

# This makes use of the interop library that needs to be installed into the Python
# VEnv - see the activate_venv script.
# Due to the way the files are read I'm making this a one-shot thing that always
# outputs all the reports. Rely on summarize_yield.py to name the files as expected.
# Arguments it takes are: <run_dir> [out_dir] [always_dump]
# Make the rule depend on the InterOp dir to spot changes, even though the script
# takes the parent dir as the input.
# Added on 9019-03-04 - we need a further input dependency as run 190228_M05898_0062_000000000-C9H28
# revealed a race condition, but we can only depend on the QMetricsOut.bin file if it exists.
rule interop_yield_table:
    output:
        tables = expand( "QC/{rep}/summarize_yield_{rep}_mqc.yaml", rep=allreps ),
        yaml   = "QC/yield.yml"
    input:
        idir = format("{SEQDATA}/InterOp"),
        qmetrics = glob(format("{SEQDATA}/InterOp/QMetricsOut.bin"))
    shell: "summarize_yield.py {input.idir}/.. QC 1 > {output.yaml}"

# md5summer that keeps the file path out of the .md5 file
rule md5sum_file:
    priority: 50
    output: "md5sums/{foo}.md5"
    input: "{foo}"
    shell: '( cd "$(dirname {input:q})" && md5sum -- "$(basename {input:q})" ) > {output:q}'

# along with the md5sums, make a count summary per file
# For speed, we're actually reading these from the Stats.json file (the
# original copy).
localrules: base_count_file
rule base_count_file:
    priority: 100
    output: "counts/{fq}.count"
    input:
        fq = "{fq}.gz",
        json = lambda wc: "demultiplexing/lane{}/Stats/Stats.json".format(split_fq_name(wc.fq)['lane'])
    shell:
        "fq_base_counter.py -j {input.json} {input.fq} > {output}"

# cutadapt used only for adapter dimer/short insert detection on read 1 only
# I'm not making the list of adapters configurable since they are supposed to be generic for all
# runs. More detailed analysis belongs in project QC.
# Note the use of 20+ bases allows detection where the first two bases are missing, with the default
# cutadapt tolerance of 10% mismatches.
rule cutadapt_scan:
    output: "QC/lane{l,[0-9]+}/{fq}.cutadapt_out"
    input:  "{fq}.fastq.gz"
    shadow: 'minimal'
    params:
        # 3' adapters: truseq 21 bases          nextera         illumina_smallrna
        adapters =    ["AGATCGGAAGAGCACACGTCT", "CTGTCTCTTATA", "TGGAATTCTCGGGTGCCAAGG"]
    shell:
        """{TOOLBOX} cutadapt -O 9 -o /dev/null `for a in {params.adapters} ; do echo -a $a ; done` \
             {input} > {output}
        """

# fastqscreen also on only read1 until I hear otherwise (--paired was removed in version 0.5)
# because of temporary files, run in a shallow shadow then move the results to the right dir
rule fqscreen:
    output:
        txt  = "QC/lane{l,[0-9]+}/{fq}_screen.txt",
        html = "QC/lane{l,[0-9]+}/{fq}_screen.html",
        png  = "QC/lane{l,[0-9]+}/{fq}_screen.png"
    input: "{fq}.fastq.gz"
    shadow: 'minimal'
    params:
        maxlen = 50,
        subset = 1000000,
    threads: 2  # Can be >1 now the bug in Bowtie is fixed!
    shell:
        """set +o pipefail
           _slen=`zcat {input} | head -n 2 | awk 'NR==2{{print length($1)}}'`
           if [ -n "$_slen" ] && [ "$_slen" -gt "{params.maxlen}" ] ; then
                _trim=$(($_slen - {params.maxlen})) ; else _trim=0
           fi
           set -x
           {TOOLBOX} fastq_screen --threads {threads} --subset {params.subset} \
            --bowtie "--trim3 $_trim" {input}
           for f in {output} ; do
                mv -t `dirname $f` `basename $f`
           done
        """

# fastqc runs on single FASTQ files, not read pairs. Apparently this is as it should be.
rule fastqc:
    output: zip = "QC/lane{l,[0-9]+}/{fq}_fastqc.zip",
            html = "QC/lane{l,[0-9]+}/{fq}_fastqc.html"
    input:  "{fq}.fastq.gz"
    shadow: 'minimal'
    shell:
        "{TOOLBOX} fastqc {input} --outdir `dirname {output.zip}` --noextract --nogroup"

# Meta-data to go at the top of the MultiQC report.
# this can change as the pipeline runs so make the rule depend on the pipeline
# directory. Also there is only one metadata file per run, not per lane, but it will be
# symlinked by multiqc_main to be picked up on all lanes and appear at the top of every
# page of the report.
localrules: summarize_for_overview, summarize_post_bcl2fastq, get_lane_summary, get_project_summary
rule summarize_for_overview:
    output: "QC/run_info.{runid}.1.yml"
    input:
        pipedir = SEQDATA + "/pipeline",
        summary = SEQDATA + "/pipeline/sample_summary.yml"
    shell:
        "summarize_for_overview.py {SEQDATA} > {output}"

# post-run metadata is per lane and also overall. Should be updated if ever
# the demultiplexing directory contents change
rule summarize_post_bcl2fastq:
    output: "QC/{lane,lane.|overview}/run_info.{runid}.2.yml"
    input: lanedir = lambda wc: f"demultiplexing/{wc.lane}/Stats/Stats.json" \
                                if wc.lane.startswith('lane') else \
                                glob(f"demultiplexing/lane?/Stats/Stats.json")
    shell:
        "summarize_post_bcl2fastq.py --lane {wildcards.lane} > {output}"

# lane summary is just a munge of the .yml already made by the driver,
# but this time we need a special mqc table format.
# re-using this saves another call out to the LIMS
# Extra columns will get added as they become available - yield (from interop)
# and well dups (from read1 processing).
rule get_lane_summary:
    output: "QC/overview/lane_summary_{runid}_mqc.yaml"
    input:
        samples_yaml   = SEQDATA + "/pipeline/sample_summary.yml",
        well_dups_yaml = ifexists("QC/welldups/*summary.yml", single=True),
        yield_yaml     = ifexists("QC/yield.yml"),
        b2f_yaml       = ifexists("QC/bcl2fastq_stats.yml")
    shell:
        """summarize_lane_contents.py --from_yml {input.samples_yaml} --mqc {output} \
           --add_in_yaml wd={input.well_dups_yaml} yield={input.yield_yaml} \
                         b2f={input.b2f_yaml}
        """

# You could edit this rule according to the outputs we actually want to see in the Overview
# report. However the "eliminate boring plots" logic should negate the need for that.
# If you want to re-order them you'll need to edit how the script generates the id since this
# is used as the sort key.
# Note that these will be re-generated if sample_summary.yml is newer, so deleting
# sample_summary.yml then re-running QC is a good way to force these to be recalculated.
rule get_project_summary:
    output:
        frag_pool = "QC/overview/matrix_of_frag_by_pool_mqc.yaml",
        frag_proj = "QC/overview/matrix_of_frag_by_proj_mqc.yaml",
        lib_pool  = "QC/overview/matrix_of_lib_by_pool_mqc.yaml",
        lib_proj  = "QC/overview/matrix_of_lib_by_proj_mqc.yaml",
        bal_pool  = "QC/overview/matrix_of_bal_by_pool_mqc.yaml",
        bal_proj  = "QC/overview/matrix_of_bal_by_proj_mqc.yaml",
    input:
        samples_yaml = SEQDATA + "/pipeline/sample_summary.yml",
        json         = expand("QC/lane{l}/Stats.json", l=lanes) or 'No FASTQ files found'
    shell:
        """summarize_by_project.py --sample_summary {input.samples_yaml} \
                --mqc_frag_pool {output.frag_pool} --mqc_frag_proj {output.frag_proj} \
                --mqc_lib_pool  {output.lib_pool}  --mqc_lib_proj  {output.lib_proj} \
                --mqc_bal_pool  {output.bal_pool}  --mqc_bal_proj  {output.bal_proj} \
                -- {input.json}
        """

localrules: get_bcl2fastq_stats_old, get_bcl2fastq_stats
rule get_bcl2fastq_stats_old:
    # FIXME - This rule should be replaced by get_bcl2fastq_stats which reads
    # Stats.json, but just now some QC reports rely on having the file in the old
    # format (this includes RapidQC). Once they are fixed and tested this can simply
    # be removed.
    # The parameters passed to the script are a little weird as I copied the script
    # from the old pipeline where it scanned for the input file.
    output: "QC/lane{lane}/{runid}_{lane}.stats.yml"
    input: "demultiplexing/lane{lane}/Stats/FastqSummaryF1L{lane}.txt"
    shell:
        "grab_bcl2fastq_stats.py demultiplexing/lane{wildcards.lane} {wildcards.runid} {wildcards.lane} > {output}"

rule get_bcl2fastq_stats:
    # If no FASTQ files were found and yet demultiplexing stats are requested, this
    # rule will end up being run with no input. Hence the dummy input acts as an error
    # message.
    output: "QC/bcl2fastq_stats.yml"
    input:
        json = expand("QC/lane{l}/Stats.json", l=lanes) or 'No FASTQ files found'
    shell:
        "stats_json_aggregator.py {input.json} > {output}"

localrules: get_bcl2fastq_json
rule get_bcl2fastq_json:
    # Simply copies the file into place, for MultiQC to find
    # Doing it this way accords with the principle that everything in the QC directory
    # should be created by this Snakefile (or Snakefile.read1qc, but not Snakefile.demux).
    output: "QC/lane{lane}/Stats.json"
    input: "demultiplexing/lane{lane}/Stats/Stats.json"
    shell: "cp {input} {output}"

localrules: get_unassigned
rule get_unassigned:
    # Replaces the old silly unassigned report with something a lot simpler and more useful
    output: "QC/lane{lane}/{run}_{lane}_unassigned_table.txt"
    input:  "demultiplexing/lane{lane}/Stats/Stats.json"
    shell:
        "unassigned_to_table.py {input} > {output}"

# === Target rules ===
rule md5_main:
    # Checksumming is done at the start of QC, but probably it should be done
    # at the end of demultiplexing.
    input:
        md5      = expand( 'md5sums/{fq[fname]}.fastq.gz.md5', fq=all_all ),
        counts   = expand( 'counts/{fq[fname]}.fastq.count',   fq=all_all )

rule interop_main:
    # Interop files in eg. /lustre/seqdata/170627_D00261_0417_ACAU93ANXX/InterOp/
    # The location will be inferred from SEQDATA/InterOp
    input:
        plots  = expand( "QC/overview/interop/{plot}.interop_plot",
                         run = [RUN],
                         plot = ['qscore_heatmap', 'by_cycle', 'by_lane', 'flowcell_all' ] ),
        ytable = expand( "QC/{rep}/summarize_yield_{rep}_mqc.yaml", rep=allreps ),
        yyaml  = "QC/yield.yml"

rule demux_stats_main:
    # Gather stats from the bcl2fastq logs etc. Calculate barcode balance, ...
    # We have the new Stats.json to compete with our old per-lane stats.yml derived
    # from the CSV output. A little confusing - do we need both? See the note on
    # get_bcl2fastq_stats_old.
    input:
        stats    = "QC/bcl2fastq_stats.yml",
        oldstats = expand("QC/lane{l}/{r}_{l}.stats.yml",  l=lanes, r=[RUN]),
        json     = expand("QC/lane{l}/Stats.json",         l=lanes),
        unass    = expand("QC/lane{l}/{r}_{l}_unassigned_table.txt", l=lanes, r=[RUN]),
        runinfo  = expand("QC/{rep}/run_info.{r}.2.yml",   rep=allreps, r=[RUN]),
        matrices = rules.get_project_summary.output

rule metadata_main:
    # Assemble the metadata items for the run. Query the LIMS if necessary.
    input:
        runinfo  = rules.run_multiqc.input.runinfo,
        laneinfo = "QC/overview/lane_summary_{r}_mqc.yaml".format(r=RUN)

rule qc_main:
    # QC inspects the actual fastq.gz files but also depends on interop and
    # demux stats which we probably already made earlier.
    input:
        cutadapt = expand( 'QC/lane{fq[lane]}/{fq[fname]}.cutadapt_out',  fq=all_1_fq ),
        fastqc   = expand( 'QC/lane{fq[lane]}/{fq[fname]}_fastqc.zip',    fq=all_fq ),
        fqscreen = expand( 'QC/lane{fq[lane]}/{fq[fname]}_screen.txt',    fq=all_1_fq ),
        interop  = rules.interop_main.input,
        demux    = rules.demux_stats_main.input,
        meta     = rules.metadata_main.input

