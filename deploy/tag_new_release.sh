#!/bin/sh
set -e
set -u

# Shell script to help you tag a new release of the code.

# Note that this script might annoy you because is is very picky.
# It is meant to be picky!
# In particular - commit all changes to master and push
#               - add all untracked files to .gitignore
#               - don't edit version.txt by hand

# What it does...
# 1) Check that I'm on branch "master"
# 2) Check that work dir is clean
# 3) Check that version.txt corresponds to the latest tag
# 4) Suggest a new version tag
#   ---are you sure---
# 5a) echo $newversion > version.txt && git commit
# 5b) git tag
# 6) git push --tags
# 7) remind the user to now do
#     cd ~pipeline/illuminatus ; get_latest_tag.sh


listtags(){
    git log --tags --simplify-by-decoration --pretty="format:%d" |\
        grep -o 'tag: v[0-9][^,)]*' | awk '{print $2}'
}

die(){
    echo "$@" ; exit 1
}

yesno(){
    while true ; do
        read -p '[y/n] ' -n1 answer
        if [ "$answer" = 'y' -o "$answer" = 'Y' ] ; then
            echo yes ; echo >&2 ; break
        elif [ "$answer" = 'n' -o "$answer" = 'N' ] ; then
            echo no ; echo >&2 ; break
        fi
        echo '?' >&2
    done
}

git push

#1 The file .git/HEAD should contain "ref: refs/heads/master"
# However, this is subsumed into the next test.
#[ "`cat .git/HEAD`" = "ref: refs/heads/master" ] || \
#    die "You do not seem to be working on the master branch."

#2 - As well as being on master, all untracked files should be in .gitignore
# and all changes should be pushed upstream.
foo=`env LC_ALL=C git status`
[[ "$foo" =~ On.branch.master.*nothing.to.commit,.working.(directory|tree).clean ]] || \
    die $'GIT reports that not all changes are pushed on the master branch...\n'"$foo"

#3
# Find the latest tag in the repo
latest_tag="`listtags | head -n1`"

latest_version_txt=`cat version.txt`

[ -z "$latest_tag" -o "$latest_tag" = "v$latest_version_txt" ] || \
    die "Version mismatch for previous tag - $latest_tag != v$latest_version_txt."$'\n' \
        "Edit version.txt and try again."

#4
new_version=`echo "$latest_version_txt" | perl -pe 's/(\d+)$/$1+1/e'`

echo "Your current version is $latest_tag."
echo "Enter new version to release (or accept the default suggestion)"
read -p ': v' -e -i "$new_version" actual_new_version

allowedchars='0123456789._-'
if [ -z "$actual_new_version" ] || \
   [ "`echo "$actual_new_version" | perl -pe "tr/$allowedchars//dc"`" != "$actual_new_version" ]
   then
        die "Invalid or empty version string.  Can only contain $allowedchars"
fi

#5

echo "Tag v$actual_new_version will now be added and pushed to the repository,"
echo "and version.txt will be updated.  Are you sure?"
[ "`yesno`" = yes ] || die



echo "$actual_new_version" > version.txt

git commit version.txt -m "Tagging new release v$actual_new_version"
git tag "v$actual_new_version"

git push --tags
git push

echo "All done.  Now log in as the pipeline user and do:"
echo "  cd ~/illuminatus && $(dirname $(readlink -f "$BASH_SOURCE"))/get_latest_tag.sh"
