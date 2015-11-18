#!/bin/bash
original_dir=`pwd`
script=`dirname $0`
cd $script/../../api
source params
export script=`pwd`
cd $original_dir

azure storage blob list -c $CONN_STR extensions
