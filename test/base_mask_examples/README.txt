Testing for all 2016 runs in /ifs/runqc/16*, to see if the new lanemask generator works.

Here are notes on how I gathered the data in this folder...

How many of the folders have no qmakeBclToFastqLanes[1-8]+.sh file?

cd /ifs/runqc
for d in 16* ; do
   ls $d | grep -q 'qmakeBclToFastqLanes[1-8]\+.sh' || echo "Not in $d"
done

38 have no file.  These seem to be aborted runs. Ok, so let's make folders for the others.

for d in 16* ; do ls -f $d | grep -q 'qmakeBclToFastqLanes[1-8]\+.sh' && ( mkdir /home/tbooth2/workspace/illuminatus/test/base_mask_examples/$d ; cp -v $d/qmakeBclToFastqLanes*[12345678].sh /home/tbooth2/workspace/illuminatus/test/base_mask_examples/$d ) ; done

Now, how many of these new folders have more than one file in them?? None. Cool.

Now I need to extract a mapping of lane->basemask from the commands.

for f in  */*.sh ; do perl -ne 'while(<>){ if(/--tiles=s_\[(\d+)\]/) { $lanes = $1; ($lm) = /--use-bases-mask (\S+) /;  print(map {"$_ $lm\n"} split(//,$lanes)) } } ' <$f >`dirname $f`/lanemasks.txt ; done

I note that many of these files are empty. These seem to correspond to runs with the old pipeline that run 'make' rather than
bcl2fastq directly.

for f in */lanemasks.txt ; do [ -s $f ] || ( grep -q -- 'make -j' `dirname $f`/*.sh && rm -r `dirname $f` ) ; done

OK

If there is an ambiguous basemask this is an error, since we've been told not to support variable-length barcodes in the new system.
I'll find these files and deal with them manually:

for f in */lanemasks.txt ; do l1="`awk '{print $1}' <$f | sort`" ; l2="`awk '{print $1}' <$f | sort -u`" ; [ "$l1" = "$l2" ] || echo $f ; done

I've added lines like '1 AMBIGUOUS' for all of these.

Cool. Now pull in the SampleSheet and RunInfo files too.

for f in * ; do cp /ifs/seqdata/$f/SampleSheet.csv $f && cp /ifs/seqdata/$f/RunInfo.xml $f ; done
for f in * ; do cp /ifs/seqdata/2016/$f/SampleSheet.csv $f && cp /ifs/seqdata/2016/$f/RunInfo.xml $f ; done

OK, we're missing some stuff. What's missing? Some of the folders only have a SampleSheet.bak in them. No probs - I'll use that.
Hopefully that doesn't introduce any junk. Now I have 720 files to test.

---

Now for the actual tests. It's a bit hacky, but you can make tests dynamically so I've set it up so that
each of thse folders will be a separate test, and each test will have 1-8 assertions, driven by the lines in
lanemasks.txt. The .sh scripts aren't examined by the tests but are kept for reference.


