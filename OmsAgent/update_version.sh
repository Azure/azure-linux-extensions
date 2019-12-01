#! /bin/bash
set -x

if [[ "$1" == "--help" ]]; then
    echo "update_version.sh <MAJOR> <MINOR> <PATH> <BUILDNR>"
    exit 0
fi

UPDATE_DATE=`date +%Y%m%d`
OMS_BUILDVERSION_MAJOR=$1
OMS_BUILDVERSION_MINOR=$2
OMS_BUILDVERSION_PATCH=$3
OMS_BUILDVERSION_BUILDNR=$4

if [[ "$OMS_BUILDVERSION_MAJOR" == "" ]]; then
    echo "MAJOR version is empty"
    exit 1
fi

if [[ "$OMS_BUILDVERSION_MINOR" == "" ]]; then
    echo "MINOR version is empty"
    exit 1
fi

if [[ "$OMS_BUILDVERSION_PATCH" == "" ]]; then
    echo "PATH version is empty"
    exit 1
fi

if [[ "$OMS_BUILDVERSION_BUILDNR" == "" ]]; then
    echo "BUILDNR version is empty"
    exit 1
fi


sed -i "s/^OMS_VERSION_MAJOR=.*$/OMS_VERSION_MAJOR=$OMS_BUILDVERSION_MAJOR/" omsagent.version
sed -i "s/^OMS_VERSION_MINOR=.*$/OMS_VERSION_MINOR=$OMS_BUILDVERSION_MINOR/" omsagent.version
sed -i "s/^OMS_VERSION_PATCH_EXTENSION=.*$/OMS_VERSION_PATCH_EXTENSION=$OMS_BUILDVERSION_PATCH/" omsagent.version
sed -i "s/^OMS_VERSION_PATCH_SHELL_BUNDLE=.*$/OMS_VERSION_PATCH_SHELL_BUNDLE=$OMS_BUILDVERSION_PATCH/" omsagent.version
sed -i "s/^OMS_VERSION_BUILDNR_SHELL_BUNDLE=.*$/OMS_VERSION_BUILDNR_SHELL_BUNDLE=$OMS_BUILDVERSION_BUILDNR/" omsagent.version
sed -i "s/^OMS_VERSION_DATE=.*$/OMS_VERSION_DATE=$UPDATE_DATE/" omsagent.version
