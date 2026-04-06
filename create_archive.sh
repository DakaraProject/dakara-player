#!/bin/bash

# strict mode
set -eu

PACKAGE_NAME="dakara_player"

# getting version of the package
version=$(python -c "from $PACKAGE_NAME import __version__; print(__version__)")
echo "Creating archive for $PACKAGE_NAME v$version"

# install twine
pip install --upgrade twine build

# clean the dist directory
rm -rf dist/*

# create the distribution packages
python -m build

# upload to PyPI
echo "Copy pase the following command (with correct repository) to upload $PACKAGE_NAME v$version to Pypi:"
echo "  python -m twine upload --repository *** dist/*"
