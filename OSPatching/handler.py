#!/usr/bin/python
#
# OSPatching extension
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
# Requires Python 2.4+


import os
import sys
import re
import platform
import shutil
import traceback

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
from patch import *

# Global variables definition
ExtensionShortName = 'OSPatching'

def install():
    hutil.do_parse_context('Install')
    try:
        MyPatching.install()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded.')
    except Exception, e:
        hutil.error("Failed to install the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '0', 'Install Failed.')

def enable():
    hutil.do_parse_context('Enable')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]\
                           ['handlerSettings'].get('protectedSettings')
        MyPatching.parse_settings(protect_settings)
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        MyPatching.enable()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded. Current Configuation: ' + current_config)
    except Exception, e:
        current_config = MyPatching.get_current_config()
        hutil.error("Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '0', 'Enable Failed. Current Configuation: ' + current_config)

def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall Succeeded.')

def disable():
    hutil.do_parse_context('Disable')
    try:
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        MyPatching.disable()
        hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded.')
    except Exception, e:
        hutil.error("Failed to disable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Disable', 'error', '0', 'Disable Failed.')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded.')

def download():
    hutil.do_parse_context('Download')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]\
                           ['handlerSettings'].get('protectedSettings')
        MyPatching.parse_settings(protect_settings)
        MyPatching.download()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0,'Enable','success','0', 'Download Succeeded. Current Configuation: ' + current_config)
    except Exception, e:
        current_config = MyPatching.get_current_config()
        hutil.error("Failed to download updates with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Download Failed. Current Configuation: ' + current_config)

def patch():
    hutil.do_parse_context('Patch')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]\
                           ['handlerSettings'].get('protectedSettings')
        MyPatching.parse_settings(protect_settings)
        MyPatching.patch()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0,'Enable','success','0', 'Patch Succeeded. Current Configuation: ' + current_config)
    except Exception, e:
        current_config = MyPatching.get_current_config()
        hutil.error("Failed to patch with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Patch Failed. Current Configuation: ' + current_config)

def oneoff():
    hutil.do_parse_context('Oneoff')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]\
                           ['handlerSettings'].get('protectedSettings')
        MyPatching.parse_settings(protect_settings)
        MyPatching.patch_one_off()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0,'Enable','success','0', 'Oneoff Patch Succeeded. Current Configuation: ' + current_config)
    except Exception, e:
        current_config = MyPatching.get_current_config()
        hutil.error("Failed to one-off patch with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Oneoff Patch Failed. Current Configuation: ' + current_config)

# Main function is the only entrance to this extension handler
def main():
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName))

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error,
                                ExtensionShortName)
    global MyPatching
    MyPatching = GetMyPatching(hutil)
    if MyPatching == None:
        sys.exit(1)

    for a in sys.argv[1:]:
        if re.match("^([-/]*)(disable)", a):
            disable()
        elif re.match("^([-/]*)(uninstall)", a):
            uninstall()
        elif re.match("^([-/]*)(install)", a):
            install()
        elif re.match("^([-/]*)(enable)", a):
            enable()
        elif re.match("^([-/]*)(update)", a):
            update()
        elif re.match("^([-/]*)(download)", a):
            download()
        elif re.match("^([-/]*)(patch)", a):
            patch()
        elif re.match("^([-/]*)(oneoff)", a):
            oneoff()


if __name__ == '__main__':
    main()
