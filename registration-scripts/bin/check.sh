#!/bin/bash

original_dir=`pwd`
script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
cd $original_dir

echo "Check Request: $1"
$root/api/check-request-status.sh 2>>/tmp/restoutput $1 | sed -e 's/></>\n</g'

