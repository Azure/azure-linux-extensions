#! /bin/bash
set -e
source omsagent.version

usage()
{
    local basename=`basename $0`
    echo
    echo "$basename <PATH_TO_OMSAGENT_SHELL_BUNDLE>"
}

bundle_path=$1
output_path=$2
PACKAGE_NAME="oms$OMS_EXTENSION_VERSION.zip"
if [[ "$1" == "--help" ]]; then
    usage
    exit 0
elif [[ ! -f $bundle_path ]]; then
    echo "OMS bundle '$bundle_path' not found"
    exit 1
fi

if [[ "$output_path" == "" ]]; then
    output_path="../"
fi

# Packaging starts here
cp -r ../Utils .
cp ../Common/WALinuxAgent-2.0.16/waagent .

# cleanup packages
rm -rf packages
mkdir -p packages
# copy shell bundle to packages/
cp $bundle_path packages/
# sync the file copy
sync

if [[ -f $output_path/$PACKAGE_NAME ]]; then
    echo "Removing existing $PACKAGE_NAME ..."
    rm -f $output_path/$PACKAGE_NAME
fi

echo "Packaging extension $PACKAGE_NAME to $output_path"
excluded_files="omsagent.version packaging.sh apply_version.sh update_version.sh"
zip -r $output_path/$PACKAGE_NAME * -x $excluded_files "./Fairfax/*" "./Mooncake/*" "./test/*" "./extension-test/*" "./references"

# cleanup newly added dir or files
rm -rf Utils/ waagent