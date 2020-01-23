#!/bin/bash

set +e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

# moving to the source root folder
cd ..
echo "Source root folder: " + $PWD

# moving to the ADE source folder
cd VMEncryption
echo "ADE source folder: " + $PWD

# updating version.txt file from CDPx generated version
# https://onebranch.visualstudio.com/Pipeline/_wiki/wikis/Pipeline.wiki/325/Versioning?anchor=%60%60%60cdp_file_version_numeric_noleadingzeros%60%60%60-and-%60%60%60.version%5Cnumeric.fileversion.info.noleadingzeros%60%60%60
cp ../.version/numeric.fileversion.info.noleadingzeros main/version.txt

# invoking Python packaging
python setup.py sdist --formats=zip
