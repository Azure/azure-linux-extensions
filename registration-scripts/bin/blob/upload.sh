#!/bin/bash
original_dir=`pwd`
script=`dirname $0`
cd $script/../../api
source params
export script=`pwd`
cd $original_dir

zip_file=$(readlink -f $1)
if [ ! -f $zip_file ] ; then
    echo "File not found: $zip_file"
    exit 1
fi
file_name=$(basename $zip_file)
echo "Uploading $zip_file to azure..."
azure storage blob upload -c $CONN_STR $zip_file extensions $file_name
