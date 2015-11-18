#!/bin/bash

original_dir=`pwd`
script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
cd $original_dir

echo "Update extension: $1"
$root/api/update-extension.sh 2>/tmp/restoutput $1 | sed -e 's/></>\n</g'

echo "===================="
echo "Check request by running bin/check.sh <request-id>"
tail /tmp/restoutput
echo "===================="
echo "More info is saved in /tmp/restoutput"
