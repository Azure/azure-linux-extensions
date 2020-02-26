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
# BUGBUG: Keeping the static version until we figure out the versioning strategy (PBI 6218633)
# echo CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS > main/version.txt

# Extension name override if specified in the YAML file
echo "Extension name: [$1]"

if [ "$1" ]
then
    echo "$1" > main/extension_name.txt
else
    echo "No extension name specified"
fi

# invoking Python packaging
python setup.py sdist --formats=zip
