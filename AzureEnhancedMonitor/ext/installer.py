#!/usr/bin/env python
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

import imp
import os
import shutil

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as util

ExtensionShortName = 'AzureEnhancedMonitor'

def parse_context(operation):
    hutil = util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context(operation)
    return hutil

def find_psutil_build(buildDir):
    for item in os.listdir(buildDir):
        try:
            build = os.path.join(buildDir, item)
            binary = os.path.join(build, '_psutil_linux.so')
            imp.load_dynamic('_psutil_linux', binary)
            return build
        except Exception:
            pass
    raise Exception("Available build of psutil not found.")

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("{0} started to handle.".format(ExtensionShortName))
    
    hutil = parse_context("Install")
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        buildDir = os.path.join(root, "libpsutil")
        build = find_psutil_build(buildDir) 
        for item in os.listdir(build):
            src = os.path.join(build, item)
            dest = os.path.join(root, item)
            if os.path.isfile(src):
                if os.path.isfile(dest):
                    os.remove(dest)
                shutil.copyfile(src, dest)
            else:
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
    except Exception as e:
        hutil.error("{0}, {1}").format(e, traceback.format_exc())
        hutil.do_exit(1, "Install", 'failed','0', 
                      'Install failed: {0}'.format(e))

if __name__ == '__main__':
    main()
