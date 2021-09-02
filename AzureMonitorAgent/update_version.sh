#! /bin/bash
set -x

if [[ "$1" == "--help" ]]; then
    echo "update_version.sh <AGENT_VERSION> <MDSD_DEB_PACKAGE_NAME> <MDSD_RPM_PACKAGE_NAME>"
    exit 0
fi

UPDATE_DATE=`date +%Y%m%d`
AGENT_VERSION=$1
MDSD_DEB_PACKAGE_NAME=$2
MDSD_RPM_PACKAGE_NAME=$3

if [[ "$AGENT_VERSION" == "" ]]; then
    echo "AGENT_VERSION version is empty"
    exit 1
fi

if [[ "$MDSD_DEB_PACKAGE_NAME" == "" ]]; then
    echo "MDSD_DEB_PACKAGE_NAME is empty"
    exit 1
fi

if [[ "$MDSD_RPM_PACKAGE_NAME" == "" ]]; then
    echo "MDSD_RPM_PACKAGE_NAME is empty"
    exit 1
fi


sed -i "s/^AGENT_VERSION=.*$/AGENT_VERSION=$AGENT_VERSION/" agent.version
sed -i "s/^MDSD_DEB_PACKAGE_NAME=.*$/MDSD_DEB_PACKAGE_NAME=$MDSD_DEB_PACKAGE_NAME/" agent.version
sed -i "s/^MDSD_RPM_PACKAGE_NAME=.*$/MDSD_RPM_PACKAGE_NAME=$MDSD_RPM_PACKAGE_NAME/" agent.version
sed -i "s/^AGENT_VERSION_DATE=.*$/AGENT_VERSION_DATE=$UPDATE_DATE/" agent.version
