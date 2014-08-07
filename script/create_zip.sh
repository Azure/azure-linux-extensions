#!/bin/bash
#
# This script is used to set up a test env for extensions
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
if [ ! $1 ]  ; then
    echo "" 
    echo "    Usage: create_zip.sh <path_to_extension_dir>"
    echo ""
    exit 1
fi

if [ ! -d $1 ]  ; then
    echo "" 
    echo "    Error: Couldn't find dir: $1>"
    echo ""
    exit 1
fi

ext_dir=$1
ext_meta=$ext_dir/HandlerManifest.json

if [ ! -f $ext_meta ] ; then
    echo ""
    echo "    Error: Couldn't find \"HandlerManifest.json\" file under $ext_dir"
    echo ""
    exit 1
fi

cur_dir=`pwd`
script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
util_dir=$root/Utils

ext_name=`grep 'name' $ext_meta | sed 's/[\"| |,]//g' |gawk -F ':' '{print $2}'`
ext_version=`grep 'version' $ext_meta | sed 's/[\"| |,]//g' |gawk -F ':' '{print $2}'`

if [ ! $ext_name ] ; then
    echo ""
    echo "    Error: Couldn't detect extention name: $ext_name"
    echo ""
    exit 1
fi

if [ ! $ext_version ] ; then
    echo ""
    echo "    Error: Couldn't detect extention version: $ext_version"
    echo ""
    exit 1
fi

ext_full_name=$ext_name-$ext_version
tmp_dir=/tmp/$ext_full_name

echo "Create zip for $ext_name version $ext_version"

echo "Creat tmp dir: $tmp_dir"
mkdir $tmp_dir

echo "Copy files..."
cp -r $ext_dir/* $tmp_dir
cp -r $util_dir $tmp_dir

echo "Switch to tmp dir..."
cd $tmp_dir

echo "Remove test dir..."
rm -r test
rm -r */test
rm *.pyc

echo "Create zip..."
zip -r $cur_dir/$ext_full_name.zip .

echo "Delete tmp dir..."
rm $tmp_dir -r
echo "Done!"
