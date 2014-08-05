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


script=$(dirname $0)
root=$script/..
cd $root
root=`pwd`
lib_path="."

echo "\$PYTHONPATH=$PYTHONPATH"

if [ ! `echo $PYTHONPATH | grep $root` ] ; then
    lib_path=$lib_path:$root
fi

if [ $lib_path != "." ] ; then
    echo "echo \"export PYTHONPATH=\$PYTHONPATH:$lib_path\" >> /etc/bash.bashrc"
    echo "export PYTHONPATH=\$PYTHONPATH:$lib_path" >> /etc/bash.bashrc
    echo "Enviroment variable PYTHONPATH has been set."
    echo "Run \"bash\" to reload bash."
else
    echo "Your enviroment is cool. No action required."
fi
