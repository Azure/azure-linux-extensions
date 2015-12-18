#!/bin/bash

original_dir=`pwd`
script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
cd $original_dir

echo "List extensions: $1"
$root/api/list-extension.sh 2>/tmp/restoutput | sed -e 's/></>\n</g' | sed -e 's/<\/ExtensionImage>/<\/ExtensionImage>\n/g'
