#!/bin/bash

set -e

# server version
if [[ -z $1 ]]
then
    >&2 echo 'Error: no version specified'
    exit 1
fi

# next server version
if [[ -z $2 ]]
then
    >&2 echo 'Error: no next version specified'
    exit 1
fi

version_number=$1
dev_version_number=$2-dev
version_date=$(date -I -u)

# patch version in setup.cfg
setup_file=setup.cfg
sed -i "s/^version = .*$/version = $version_number/" $setup_file

# patch version date in version file
version_file=src/dakara_player_vlc/version.py
sed -i "s/^__date__ = .*$/__date__ = \"$version_date\"/" $version_file

# change version in changelog
changelog_file=CHANGELOG.md
sed -i "/^## Unreleased$/a \\
\\
## $version_number - $version_date" $changelog_file

# change version in appveyor config file
appveyor_file=.appveyor.yml
sed -i "s/^version: .*-{build}$/version: $version_number-{build}/" $appveyor_file

# create commit and tag
git add $setup_file $version_file $changelog_file $appveyor_file
git commit -m "Version $version_number" --no-verify
git tag "$version_number"

# say something
echo "Version bumped to $version_number"

# patch dev version in setup.cfg
sed -i "s/^version = .*$/version = $dev_version_number/" $setup_file

# change version in appveyor config file
sed -i "s/^version: .*-{build}$/version: $dev_version_number-{build}/" $appveyor_file

# create commit
git add $setup_file $appveyor_file
git commit -m "Dev version $dev_version_number" --no-verify

# say something
echo "Updated to dev version $dev_version_number"
