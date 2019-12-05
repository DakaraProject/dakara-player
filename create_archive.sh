#!/bin/bash

# strict mode
set -eu

# getting version of the package
version=$(python setup.py --version)
echo "Creating archive for dakara_player_vlc v$version"

# install twine
pip install --upgrade twine

# clean the dist directory
rm -rf dist/*

# create the distribution packages
python setup.py sdist bdist_wheel

# upload to PyPI
echo "Package will be uploaded tp Pypi"
python -m twine upload dist/*
