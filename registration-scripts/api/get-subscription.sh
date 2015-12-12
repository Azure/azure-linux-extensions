#!/bin/bash
original_dir=`pwd`
script=`dirname $0`
cd $script
source params
export script=`pwd`
cd $original_dir

echo "GET $ENDPOINT/$SUBSCRIPTION"

curl -v -X 'GET' --keepalive-time 30 --user-agent ' Microsoft.WindowsAzure.Management.Compute.ComputeManagementClient/0.9.0.0 WindowsAzurePowershell/v0.8.0' -H 'x-ms-version: 2014-06-01' -H 'Content-Type: application/xml'  --insecure  -E $CERT $ENDPOINT/$SUBSCRIPTION
