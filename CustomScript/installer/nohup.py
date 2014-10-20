#!/usr/bin/env python
#
#CustomScript extension
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
# Requires Python 2.6+

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as util

ExtensionShortName = 'CustomScript'

def StartTask(hutil, args):
    download_dir = get_download_directory(hutil._context._seq_no)
    p = subprocess.Popen(args, cwd=download_dir, 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
    out,err = p.communicate()
    hutil.log(('The custom script is executed with the output {0}'
               'and error(if applied) {1}.').format(out,err))
    hutil.do_exit(0, 'Enable', 'success','0', 'Enable Succeeded.')

if __name__ == '__main__':
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    StartTask(hutil, system.args)
