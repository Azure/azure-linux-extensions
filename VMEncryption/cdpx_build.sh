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

# updating extension_name.txt file from CDPx environment variable if defined
echo "Extension name variable: $ADE_EXTENSION_NAME_OVERRIDE"

if [ -v ADE_EXTENSION_NAME_OVERRIDE ]
then
    echo $ADE_EXTENSION_NAME_OVERRIDE > main/extension_name.txt
else
    echo "Variable ADE_EXTENSION_NAME_OVERRIDE doesn't have any value"
fi

# invoking Python packaging
python setup.py sdist --formats=zip
