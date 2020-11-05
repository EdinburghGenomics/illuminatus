#!/bin/bash

# This helps you get a new version from GIT and deploy it
# to ~pipeline/illuminatus on GSEG.  Change to that directory
# before running it.
# It is "safe" in that it won't clobber anything.  I promise.

# To prep for first release:
#  git init --bare --shared git_repo
#  git --git-dir=git_repo remote add origin git@github.com:EdinburghGenomics/illuminatus.git
#  git --git-dir=git_repo fetch --all

die(){ echo $@ ; exit 1 ; }
runcmd(){ echo "RUNNING: $@" ; "$@" ; }

# Sanity checking stage...
[ -d git_repo ] || die "No git_repo folder."\
    "This script should normally be run in /lustre/home/pipeline/illuminatus/"

# Update the git_repo.  This doesn't affect any actual working files.
# Note - if the tag doesn't appear to be fetched then make sure you
# tagged it on the master branch!
runcmd git --git-dir=git_repo fetch --all
runcmd git --git-dir=git_repo repack -ad

#Note this assumes the tags are all of the form v0.0.0 and ignores others.
#The top tag will be the latest.
listtags(){
    git --git-dir=git_repo log --tags --simplify-by-decoration --pretty="format:%d" |\
        grep -o 'tag: v[0-9][^,)]*' | awk '{print $2}'
}

# Find the latest tag in the repo
latest_tag="`listtags | head -n1`"

# Find the latest tag from the repo for which there is a directory
latest_checked_out="NONE"
for tag in `listtags` ; do
    if [ -e "$tag" ] ; then
        latest_checked_out="$tag"
        break
    fi
done

# Check we saw something
[ -z "$latest_tag" ] && die "No tags found in GIT"

# See if the latest tag already exists as a directory
[ -d "$latest_tag" ] && die "The latest tag - $latest_tag - is already checked out."

# So we know there is no folder for latest_tag, it's safe to create one and populate it
runcmd mkdir "$latest_tag"
runcmd git --git-dir=git_repo --work-tree="$latest_tag" checkout -f tags/"$latest_tag"

# Copy the config file
cp -vn -t $latest_tag $latest_checked_out/environ.sh

# Finally, alert the user if there were local changes in $latest_checked_out

# Sanity check
[ -d "$latest_checked_out" ] || die "Could not read folder for tag $latest_checked_out"

if git --git-dir=git_repo --work-tree="$latest_checked_out" diff tags/"$latest_checked_out" -- | grep -q '' ; then
    echo "WARNING - unexpected difference between the files in $latest_checked_out/ and the matching tag in GIT!"
    echo "Maybe somebody did a cheeky in-place edit?"
    echo "To check:"
    echo "  git --git-dir=git_repo --work-tree=$latest_checked_out diff tags/$latest_checked_out"
    echo
fi

echo "Checked out version $latest_tag.  If you are happy, check the config and bootstrap the virtualenv now:"
echo "  cd `pwd`"
echo "  cat $latest_tag/environ.sh"
echo "  (cd $latest_tag && source ./activate_venv )"
echo "  ln -snf $latest_tag current"
