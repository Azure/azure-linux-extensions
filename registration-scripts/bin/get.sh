#!/bin/bash
original_dir=`pwd`
script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
cd $original_dir

echo "Get extension: $1 $2"
$root/api/get-extension.sh 2>/tmp/restoutput $1 $2 | sed -e 's/></>\n</g'

