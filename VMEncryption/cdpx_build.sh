#!/bin/bash

set +e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

# moving to the source root folder
cd ..
echo "Source root folder: " + $PWD
SRC_ROOT=$PWD

# moving to the ADE source folder
cd VMEncryption
echo "ADE source folder: " + $PWD

# updating version.txt file from CDPx generated version
# https://onebranch.visualstudio.com/Pipeline/_wiki/wikis/Pipeline.wiki/325/Versioning?anchor=%60%60%60cdp_file_version_numeric_noleadingzeros%60%60%60-and-%60%60%60.version%5Cnumeric.fileversion.info.noleadingzeros%60%60%60
# BUGBUG: Keeping the static version until we figure out the versioning strategy (PBI 6218633)
# echo CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS > main/version.txt

if [ -z "$CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS" ]
then
echo "Variable CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS must be set with the build version."
    exit 1
fi

# Building Public EV2 artifacts
pwsh -Command $SRC_ROOT/VMEncryption/EV2/build_ev2_Linux.ps1 -srcRoot $SRC_ROOT/VMEncryption -outputDir $SRC_ROOT/VMEncryption/dist/EV2/Public -ExtensionInfoFile $SRC_ROOT/VMEncryption/EV2/ExtensionInfo.Public.xml -BuildVersion $CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS

# Building Test EV2 artifacts
pwsh -Command $SRC_ROOT/VMEncryption/EV2/build_ev2_Linux.ps1 -srcRoot $SRC_ROOT/VMEncryption -outputDir $SRC_ROOT/VMEncryption/dist/EV2/Test1 -ExtensionInfoFile $SRC_ROOT/VMEncryption/EV2/ExtensionInfo.Test1.xml -BuildVersion $CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS
pwsh -Command $SRC_ROOT/VMEncryption/EV2/build_ev2_Linux.ps1 -srcRoot $SRC_ROOT/VMEncryption -outputDir $SRC_ROOT/VMEncryption/dist/EV2/Test2 -ExtensionInfoFile $SRC_ROOT/VMEncryption/EV2/ExtensionInfo.Test2.xml -BuildVersion $CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS
pwsh -Command $SRC_ROOT/VMEncryption/EV2/build_ev2_Linux.ps1 -srcRoot $SRC_ROOT/VMEncryption -outputDir $SRC_ROOT/VMEncryption/dist/EV2/Test3 -ExtensionInfoFile $SRC_ROOT/VMEncryption/EV2/ExtensionInfo.Test3.xml -BuildVersion $CDP_FILE_VERSION_NUMERIC_NOLEADINGZEROS
