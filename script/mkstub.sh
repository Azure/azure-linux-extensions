#!/bin/bash
#
# This script is used to create stub for unit test
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
    echo "    Usage: mkstub.sh <path_to_extension_dir>"
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
waagent_path='/usr/sbin/waagent'
waagent_lib_dir='/var/lib/waagent'
ext_log_dir='/var/log/azure'

ext_name=`grep 'name' $ext_meta | sed 's/[\"| |,]//g' |gawk -F ':' '{print $2}'`
ext_version=`grep 'version' $ext_meta | sed 's/[\"| |,]//g' |gawk -F ':' '{print $2}'`

ext_full_name=$ext_name-$ext_version
ext_dir=$waagent_lib_dir/$ext_full_name
ext_status_dir=$ext_dir/status
ext_config_dir=$ext_dir/config
ext_env_json=$ext_dir/HandlerEnvironment.json
test_cert_file=$waagent_lib_dir/TEST.crt
test_pk_file=$waagent_lib_dir/TEST.prv
ovf_env_file=$waagent_lib_dir/ovf-env.xml

if [ ! -f $waagent_path ] ; then
    echo "Download latest waagent code"
    wget https://raw.githubusercontent.com/Azure/WALinuxAgent/2.0/waagent -O $waagent_path
    chmod +x $waagent_path
fi

if [ ! -d $waagent_lib_dir ] ; then
    echo "Create lib dir"
    mkdir $waagent_lib_dir
fi

if [ ! -d $ext_dir ] ; then
    echo "Create extension dir"
    mkdir $ext_dir
fi

if [ ! -d $ext_config_dir ] ; then
    echo "Create extension config dir"
    mkdir $ext_config_dir
fi

if [ ! -d $ext_status_dir ] ; then
    echo "Create extension status dir"
    mkdir $ext_status_dir
fi

if [ ! -f $ext_env_json ] ; then
    echo "Create HandlerEnvironment.json file"
    cp $script/HandlerEnvironment.json $ext_env_json
fi

if [ ! -f $test_cert_file ] ; then
    echo "Create test cert file"
    cp $script/test.crt $test_cert_file
fi

if [ ! -f $test_pk_file ] ; then
    echo "Create test pk file"
    cp $script/test.prv $test_pk_file
fi

if [ ! -f $ovf_env_file ] ; then
    echo "Create ovf-env.xml file"
    cp $script/ovf-env.xml $ovf_env_file
fi

if [ ! -f $ext_config_dir/0.settings ] ; then
    echo "Create 0.settings"
    cp $script/0.settings $ext_config_dir/0.settings
fi

if [ ! -d $ext_log_dir ] ; then
    echo "Create ext log dir"
    mkdir $ext_log_dir
fi

if [ ! -d $ext_log_dir/$ext_name ] ; then
    echo "Create ext log dir for $ext_name"
    mkdir $ext_log_dir/$ext_name
fi

if [ ! -d $ext_log_dir/$ext_name/$ext_version ] ; then
    echo "Create ext log dir for $ext_name $ext_version"
    mkdir $ext_log_dir/$ext_name/$ext_version
fi

echo "Change permission of waagent lib dir"
chmod -R 600 $waagent_lib_dir
