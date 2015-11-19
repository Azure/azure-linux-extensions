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

if [ $# != 2 ]  ; then
    echo "" 
    echo "    Usage: $0 <path-to-extension> <version>"
    echo "    Example: $0 SampleExtension 1.0.0.0"
    echo ""
    exit 1
fi

if [ ! -d $1 ]  ; then
    echo "" 
    echo "    Error: Couldn't find dir: $1"
    echo ""
    exit 1
fi

curr_dir=`pwd`
ext_dir=$1
cd $ext_dir
ext_dir=`pwd`
cd $curr_dir

script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`

util_dir=$root/Utils
build_dir=$root/build

if [ ! -d $build_dir ] ; then
    mkdir $build_dir
fi

ext_name=`echo $1 | sed 's/\/$//'`
ext_version=$2
ext_full_name=$ext_name-$ext_version
tmp_dir=$build_dir/$ext_full_name

echo "Create zip for $ext_name version $ext_version"

echo "Creat tmp dir: $tmp_dir"
mkdir $tmp_dir

echo "Copy files..."
cp -r $ext_dir/* $tmp_dir
rm $tmp_dir/references

echo "Copy dependecies..."
cat $ext_dir/references
cat $ext_dir/references | xargs cp -r -t $tmp_dir

echo "Switch to tmp dir..."
cd $tmp_dir

echo "Remove test dir..."
rm -r test
rm -r */test

echo "Remove *.pyc..."
find . -name "*.pyc" | xargs rm -f

echo "Create zip..."
zip -r $build_dir/$ext_full_name.zip .

echo "Delete tmp dir..."
rm $tmp_dir -r
echo "Done!"
