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

# /lustre/software/illuminatus_toolbox is the default place for all external deps.
# It should mostly be links (maybe a little wrapper script or two) so if you want to
# test with a new version of anything you can copy the whole directory and set $TOOLBOX in
# your test environment (maybe in environ.sh). Or for tinkering you can just edit the code
# in this file to temporarily ignore $TOOLBOX.
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
#   fq_base_counter.py, RunMetaData.py, PostRunMetaData.py, summarize_lane_contents.py, grab_bcl2fastq_stats.py
if ( not os.path.dirname(workflow.snakefile) in os.environ['PATH'].split(':') and
     not os.path.dirname(os.path.abspath(workflow.snakefile)) in os.environ['PATH'].split(':') ):
     os.environ['PATH'] += ':' + os.path.dirname(workflow.snakefile)

# DEBUG. Note that the TOOLBOX doesn't go in the PATH - you have to invoke it explicitly.
#print("PATH is {}".format(os.environ['PATH']), file=sys.stderr)

# Special case for count_unassigned, which really should be made into a separate tool and
# then put in the TOOLBOX
UNASS = os.path.dirname(workflow.snakefile) + '/unassigned_report'

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

# See what input sequences we are dealing with (if any, yet)
# I wanted to use a hack to stop this being re-run on every cluster job,
# but it didn't work as Snakemake re-runs itself even for local jobs.
all_unassigned_fq = [ split_fq_name(f) for f in glob('*_unassigned_?.fastq.gz') ]
all_assigned_fq   = [ split_fq_name(f) for f in glob('[1-9]*/*/*.fastq.gz') ]
all_control_fq    = [ split_fq_name(f) for f in glob('ControlLane/*/*.fastq.gz') ]
all_fq = (all_assigned_fq + all_unassigned_fq + all_control_fq)
all_1_fq  = [ fq for fq in all_fq if fq['read'] == '1' ]
all_u1_fq = [ fq for fq in all_unassigned_fq if fq['read'] == '1' ]

if all_fq:
    # If there are any fastq files there must be some from read 1.
    assert all_1_fq, "No read1 files found in {}, but there were {} fastq files in total.".format(
                                              os.getcwd(),       len(all_fq) )

# There should only be one run. But what is it called?
# If config['runid'] is set we use that, otherwise infer from all_fq, otherwise
# the current directory name will do.
try:
    runs = set( sf['run'] for sf in all_fq )
    if 'runid' in config: runs.add(config['runid'])
    assert len(runs) <= 1, "Expected to find only one run in {} but saw: {}".format(os.getcwd(), runs)
    run, = runs
except ValueError:
    # Revert to using name of CWD
    run = os.path.basename(os.path.realpath(os.getcwd()))
finally:
    del(runs)

lanes = sorted( set( sf['lane'] for sf in all_fq ) )
# All report names - lane1, lane2, ..., overview
# This will not generate the per-lane reports until the demultiplexing has been done.
# FIXME - stop the dangling links on the overview that will result from this.
allreps = expand("lane{l}", l=lanes) + ['overview']

# === Driver rules ===
rule md5_main:
    input:
        md5      = expand( 'md5sums/{fq[fname]}.fastq.gz.md5',  fq=all_fq ),
        counts   = expand( 'counts/{fq[fname]}.fastq.count', fq=all_fq )

# qc_main depends on other rules so it's now down below.

# Interop files in eg. /lustre/seqdata/170627_D00261_0417_ACAU93ANXX/InterOp/
# The location will be inferred from SEQDATA/InterOp
rule interop_main:
    input:
        plots  = expand( "QC/overview/interop/{plot}.interop_plot",
                         run = [run],
                         plot = ['qscore_heatmap', 'by_cycle', 'by_lane', 'flowcell' ] ),
        ytable = expand( "QC/{rep}/summarize_yield_{rep}_mqc.yaml", rep=allreps ),
        yyaml  = "QC/yield.yml"

rule demux_stats_main:
    # Gather stats from the bcl2fastq logs etc. Calculate barcode balance, ...
    # We have the new Stats.json to compete with our old per-lane stats.yml derived
    # from the CSV output. A little confusing - do we need both?
    input:
        stats    = "QC/bcl2fastq_stats.yml",
        oldstats = expand("QC/lane{l}/{r}_{l}.stats.yml", l=lanes, r=[run]),
        json     = expand("QC/lane{l}/Stats.json",        l=lanes),
        runinfo  = expand("QC/{rep}/run_info.{r}.2.yml",  rep=allreps, r=[run])

rule metadata_main:
    # TODO - assemble the metadata items for the run. Query the LIMS if necessary.
    input:
        runinfo  = "QC/run_info.{r}.1.yml".format(r=run),
        laneinfo = "QC/overview/lane_summary_{r}_mqc.yaml".format(r=run)

rule qc_main:
    # QC inspects the actual fastq.gz files but also depends on interop and
    # demux stats which we probably already made earlier.
    input:
        cutadapt = expand( 'QC/lane{fq[lane]}/{fq[fname]}.cutadapt_out',  fq=all_1_fq ),
        fastqc   = expand( 'QC/lane{fq[lane]}/{fq[fname]}_fastqc.zip',    fq=all_fq ),
        fqscreen = expand( 'QC/lane{fq[lane]}/{fq[fname]}_screen.txt',    fq=all_1_fq ),
        unass    = expand( 'QC/lane{fq[lane]}/{fq[fname]}.unassigned',    fq=all_u1_fq ),
        interop  = rules.interop_main.input,
        demux    = rules.demux_stats_main.input,
        meta     = rules.metadata_main.input

# For now run this locally. Might want to shift it to the cluster if login-0 gets too
# busy, but then the risk is arbitrary delay if the cluster is full up.
# Note this rule does not trigger qc_main etc., because we need to be able to make a
# skeleton report before we have the actual data, so you need to trigger any qc steps
# explicitly. It should be possible to run multicq_main with the -F flag (force full
# re-run) without triggering any cluster jobs, so to that end we can't depend on laneinfo,
# as this processes the InterOP stuff.
localrules: multiqc_main, run_multiqc
rule multiqc_main:
    input:
        overview = "QC/multiqc_report_overview.html",
        lanereps = expand("QC/multiqc_report_lane{l}.html", l=lanes)

rule run_multiqc:
    output:
        report = "QC/multiqc_report_{l}.html",
        data = "QC/multiqc_report_{l}_data"
    input:
        config   = "QC/multiqc_config.yml",
        #laneinfo = rules.metadata_main.input.laneinfo,
        runinfo  = rules.metadata_main.input.runinfo
    shell:
        """echo "multiqc is `which multiqc`" >&2
           rm -rf {output.data}
           ln -srf {input.runinfo} QC/{wildcards.l}/
           {TOOLBOX} multiqc -t edgen -o QC -n `basename {output.report}` -c {input.config} QC/{wildcards.l} --lane {wildcards.l}
        """

localrules: configure_multiqc
rule configure_multiqc:
    # Emits configuration for MultiQC. This may want to be split out into a separate
    # module but for now I'll just embed it here.
    output: "QC/multiqc_config.yml"
    run:
        conf = dict( title = 'placeholder',
                     intro_text = False,
                     extra_fn_clean_exts = [
                      dict( type = 'regex',
                            pattern = '\.(?:san|)fastq$' ),
                      dict( type = 'regex',
                            pattern = '(^|.*/){}_._'.format(run) ),
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
                     #Why did I add this? Oh, to only see the merged data, not the per run-element data.
                     #But it doesn't apply to run reports anyway.
                     fn_ignore_paths = [ '*__*/1*' ],
                     #Interactive plots please
                     plots_flat_numseries = 1000,
                     #Custom content
                     top_modules = [ 'custom_content', 'edgen_interop' ],
                     fastqc_config = dict(
                        plots_enabled = [ "sequence_quality_plot",
                                          "per_seq_quality_plot",
                                          #"sequence_content_plot",
                                          "gc_content_plot",
                                          "n_content_plot",
                                          "seq_dup_levels_plot" ] ),
                     fastq_screen_config = dict(
                        tack_on_images = True ),
                   )

        with open(output[0], "w") as cfh:
            print(yaml.safe_dump(conf, default_flow_style=False), file=cfh)

# === Actual data-gathering rules ===

# Presumably interop data is under {SEQDATA_LOCATION}/{runid}/InterOp
# But if there is a seqdata symlink, follow that instead.
# And as always, config takes priority over both.
SEQDATA = os.path.realpath('./seqdata')
if not os.path.isdir(SEQDATA) or ('seqdata' in config):
    # Nope, look for a match by name.
    SEQDATA = config.get('seqdata', os.path.join(os.environ.get('SEQDATA_LOCATION', '.'), run))

rule interop_qscore_heatmap:
    output: "{foo}/qscore_heatmap.interop_plot"
    input: format("{SEQDATA}/InterOp")
    shell: "{TOOLBOX} interop_plot_qscore_heatmap {input}/.. > {output}"

rule interop_by_cycle:
    output: "{foo}/by_cycle.interop_plot"
    input: format("{SEQDATA}/InterOp")
    shell: "{TOOLBOX} interop_plot_by_cycle {input}/.. > {output}"

rule interop_by_lane:
    output: "{foo}/by_lane.interop_plot"
    input: format("{SEQDATA}/InterOp")
    shell: "{TOOLBOX} interop_plot_by_lane {input}/.. > {output}"

rule interop_flowcell:
    output: "{foo}/flowcell.interop_plot"
    input: format("{SEQDATA}/InterOp")
    shell: "{TOOLBOX} interop_plot_flowcell {input}/.. > {output}"

# This makes use of the interop library that needs to be installed into the Python
# VEnv - see the activate_venv script.
# Due to the way the files are read I'm making this a one-shot thing that always
# outputs all the reports. Rely on summarize_yield.py to name the files as expected.
# Make the rule depend on the InterOp dir to spot changes, even though the script
# takes the parent dir as the input.
rule interop_yield_table:
    output:
        tables = expand( "QC/{rep}/summarize_yield_{rep}_mqc.yaml", rep=allreps ),
        yaml   = "QC/yield.yml"
    input: format("{SEQDATA}/InterOp")
    shell: "summarize_yield.py {input}/.. QC 1 > {output.yaml}"

# md5summer that keeps the file path out of the .md5 file
rule md5sum_file:
    output: "md5sums/{foo}.md5"
    input: "{foo}"
    shell: "( cd `dirname {input}` && md5sum `basename {input}` ) > {output}"

# along with the md5sums, make a count summary per file
# For speed, we're actually reading these from the Stats.json file (the
# original copy).
localrules: base_count_file
rule base_count_file:
    output: "counts/{fq}.count"
    input:
        fq = "{fq}.gz",
        json = lambda wc: "demultiplexing/lane{}/Stats/Stats.json".format(split_fq_name(wc.fq)['lane'])
    shell:
        "fq_base_counter.py -j {input.json} {input.fq} > {output}"

# cutadapt used only for adapter dimer detection on read 1
rule cutadapt_scan:
    output: "QC/lane{l,[0-9]+}/{fq}.cutadapt_out"
    input: "{fq}.fastq.gz"
    params:
        adapters = ["AGATCGGAAGAGC", "CTGTCTCTTATA"]
    shell:
        """{TOOLBOX} cutadapt -f fastq -O 9 -o /dev/null `for a in {params.adapters} ; do echo -a $a ; done` \
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
    shadow: 'shallow'
    params:
        maxlen = 50,
        subset = 1000000,
    threads: 2  # Has to be 1 until the bug in Bowtie is fixed!
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

# Even though there should simply be one per lane, do this per unassigned fastq
# to match all the other rules.
# The output is an HTML file but I can't use an .html extension because then
# MultiQC will refuse to look at it.
rule unassigned_scan:
    output: "QC/lane{l,[0-9]+}/{fq}.unassigned"
    input:
        bcs = "QC/known_barcodes.pdump",
        stats = "QC/lane{l}/Stats.json", #we can extract total reads from this
        fq = "{fq}.fastq.gz"
    threads: 2
    params:
        # See if a 4000 (or X) run. There should probably be a more generic way
        flag4000 = '-hiSeqRun4000' if run.split('_')[1][0] in 'KE' else ''
    run:
        with open(input.stats) as jfh:
            json_info = json.loads(jfh.read())

            # Normally there should be just one lane in the JSON but let's be
            # explicit anyway.
            reads_in_lane, = [ cr['TotalClustersPF'] for cr in
                               json_info['ConversionResults'] if
                               cr['LaneNumber'] == int(wildcards.l) ]

        shell("""gzip -d -c {input.fq} | \
                 {UNASS}/count -flagtablestart -noprogress -numtooutput 30 -cutoff 1500 -sortby count \
                   -loadbc {input.bcs} -reportfile {output}.tmp1 {params.flag4000}""")
        shell("""{UNASS}/count -xmlwiki -noprogress -in {output}.tmp1 -addnumlanepercent {reads_in_lane} \
                   -reportfile {output}.tmp2""")

        # Make it vaguely readable
        shell("""cat {UNASS}/page_header.html {output}.tmp2 {UNASS}/page_footer.html > {output}""")

        # Clean up.
        shell("""rm {output}.tmp{{1,2}}""")

# This rule needs to run just once on the login node.
localrules: lookup_known_barcodes
rule lookup_known_barcodes:
    output: "QC/known_barcodes.pdump"
    params:
        flag4000 = '-hiSeqRun4000' if run.split('_')[1][0] in 'KE' else ''
    shell:
        "{UNASS}/count -noprogress -savebc {output} {params.flag4000}"

# fastqc runs on single FASTQ files, not read pairs. Apparently this is as it should be.
rule fastqc:
    output: zip = "QC/lane{l,[0-9]+}/{fq}_fastqc.zip",
            html = "QC/lane{l,[0-9]+}/{fq}_fastqc.html"
    input: "{fq}.fastq.gz"
    threads: 2
    shell:
        "{TOOLBOX} fastqc {input} --outdir `dirname {output.zip}` --noextract --nogroup --threads {threads}"

# meta-data. this can change as the pipeline runs so make the rule depend on the pipeline
# directory. Also there is only one metadata file per run, not per lane, but it will be
# symlinked by multiqc_main to be picked up on all runs
localrules: get_run_metadata, get_postrun_metadata, get_lane_summary
rule get_run_metadata:
    output: "QC/run_info.{runid}.1.yml"
    input: SEQDATA + "/pipeline"
    shell:
        "RunMetaData.py {SEQDATA} > {output}"

# post-run metadata is per lane and also overall. Should be updated if ever
# the demultiplexing directory contents change
rule get_postrun_metadata:
    output: "QC/{lane,lane.|overview}/run_info.{runid}.2.yml"
    input: lanedir = lambda wc: "demultiplexing/" + wc.lane if wc.lane.startswith('lane') else \
                                glob("demultiplexing/lane?")
    shell:
        "PostRunMetaData.py . {wildcards.lane} > {output}"

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

localrules: get_bcl2fastq_stats_old, get_bcl2fastq_stats
rule get_bcl2fastq_stats_old:
    # This rule can hopefully be replaced by the direct examination of the .json
    # file by the new module for MultiQC.
    # The parameters passed to the script are a little weird as I copied the script
    # from the old pipeline where it scanned for the input file.
    output: "QC/lane{lane}/{runid}_{lane}.stats.yml"
    input: "demultiplexing/lane{lane}/Stats/FastqSummaryF1L{lane}.txt"
    shell:
        "grab_bcl2fastq_stats.py demultiplexing/lane{wildcards.lane} {wildcards.runid} {wildcards.lane} > {output}"

rule get_bcl2fastq_stats:
    output: "QC/bcl2fastq_stats.yml"
    input:
        json = expand("QC/lane{l}/Stats.json", l=lanes)
    shell:
        "stats_json_aggregator.py {input.json} > {output}"

localrules: get_bcl2fastq_json
rule get_bcl2fastq_json:
    # Straight up just copies the file into place, for MultiQC to find
    output: "QC/lane{lane}/Stats.json"
    input: "demultiplexing/lane{lane}/Stats/Stats.json"
    shell: "cp {input} {output}"
