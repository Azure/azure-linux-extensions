#!/usr/bin/python
#
# Stepping Stone extension
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
from web_console import *

# Global variables definition
EXTENSION_SHORT_NAME = 'SteppingStone'

def install():
    hutil.do_parse_context('Install')
    try:
        guacamole_installer.install_guacamole()
        guacamole_installer.configure_auth()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded')
    except Exception, e:
        hutil.error('Failed to install the extension with error: %s, '
                    'stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '0', 'Install Failed')

def enable():
    hutil.do_parse_context('Enable')
    try:
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded.')
    except Exception, e:
        hutil.error('Failed to enable the extension with error: %s, '
                    'stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '0', 'Enable Failed.')

def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall Succeeded')

def disable():
    hutil.do_parse_context('Disable')
    try:
        hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')
    except Exception, e:
        hutil.error('Failed to disable the extension with error: %s, '
                    'stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Disable', 'error', '0', 'Disable Failed')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')

# Main function is the only entrance to this extension handler
def main():
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." %(EXTENSION_SHORT_NAME))

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error,
                                EXTENSION_SHORT_NAME)
    global guacamole_installer
    guacamole_installer = get_installer(hutil)
    if guacamole_installer == None:
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


if __name__ == '__main__':
    main()
