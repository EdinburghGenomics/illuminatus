Getting the pipeline up on ULTRA2 is... fun...

First I got all the toolbox stuff working. Mostly I just copied stuff across.
For cutadapt I reinstalled via pip - now version 3 but it should work the same.

For gnuplot I got it installed by Kris
For some modules in the VEnv that won't build, I copied wheels over from edgen-login0.
It's really easy - 'pip3 wheel <modulename>' and then the resulting .whl files can
be installed with 'pip3 install *.whl'

We need to be able to see the sample sheets but I discovered I can sshfs mount the
directory off clarity.genomics.ed.ac.uk (see /home/edg01/edg01/shared/mnt) and at the
same time I can do a dirty port forward to access PostgreSQL on db2.genepool.private.

I imagine the same port forwarding shenanigans will work for getting RT API access
but I'll keep that disabled during testing to avoid extra messages in RT.
- Actually we can just access RT directly.

Can we SSH to egcloud? I can now!

What's next? I copied over two test runs in:
/home/edg01/edg01/shared/seqdata

Let's try running them. I need a suitable environ.sh
