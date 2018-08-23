#!/bin/bash

set -e

if [[ -z $1 ]]
then
    >&2 echo 'Error: no version specified'
    exit 1
fi

version_number=$1
version_date=$(date -I -u)

# change internal version file
version_file=dakara_player_vlc/version.py
cat <<EOF >$version_file
__version__ = '$version_number'
__date__ = '$version_date'
EOF

# change version in changelog
changelog_file=CHANGELOG.md
sed -i "/^## Unreleased$/a \\
\\
## $version_number - $version_date" $changelog_file

# change version in appveyor config file
appveyor_file=appveyor.yml
sed -i "s/^version: .*-{build}$/version: $version_number-{build}/" $appveyor_file

git add $version_file $changelog_file
git commit -m "Version $version_number" --no-verify
git tag $version_number

echo "Version bumped to $version_number"
