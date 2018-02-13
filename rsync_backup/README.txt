As of 9th Feb 2018, data is processed by the new Illuminatus pipeline on /lustre.

Since we are retiring the Isilon and PowerVault disks, we want our backup copy of the
precious FASTQ files to be kept on /fluidfs. I think we probably want something a little
more sophisticated than RSYNC, but for now I'm just using RSYNC (with a wrapper script).

I'll RSYNC everything from January 2018.

I'll exclude the .snakemake and slurm_output directories as these are full of pointless small
files, but I'll keep the other logs etc.

I'll only sync runs that are in status 'complete'. This means I need to be able to run the
RunStatus.py script to check that. Therefore it makes sense for the backup script to be in with
the Illuminatus code, so that is where you'll find it, along with an up-to-date version of
this file under rsync_backup/.
(Actually, no, I'll look at the touch files directly - RunStatus.py is overkill)

Note here's the rsync line being used for transfer backup, prior to the transfer server moving
to gseg-dt. It runs off /etc/cron.daily/transfer_rsync:

rsync -av /var/transfer/ /lustre/transfer/ > /root/transfer_rsync.log

I can handle my log redirection with cron_o_matic. Also if I'm only working on recent runs I can
maybe venture to use the --delete flag on RSYNC. Is that ever safe???
