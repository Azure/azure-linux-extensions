#!/bin/bash

original_dir=`pwd`
script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
cd $original_dir

echo "Get subscription"
$root/api/get-subscription.sh 2>>/tmp/restoutput | sed -e 's/></>\n</g'
