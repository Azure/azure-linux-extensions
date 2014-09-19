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
import time
import json

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from web_console.web_console_handler import WebConsoleHandler

# Global variables definition
EXTENSION_SHORT_NAME = 'SteppingStone'

DEFAULT_SETTINGS_SHELLINABOX_LOCAL = {
    "webConsoleTool" : "shellinabox",
    "isSteppingStone" : False,
    "disableSSL" : False,
    "port" : 4200
}

DEFAULT_SETTINGS_SHELLINABOX_SSS = {
    "webConsoleTool" : "shellinabox",
    "isSteppingStone" : True,
    "connections" : [
        {
            "disableSSL" : False,
            "hostname" : "localhost",
            "disabled" : False
        },
        {
            "disableSSL" : False,
            "hostname" : "sss-demo.cloudapp.net",
            "disabled" : False
        },
        {
            "disableSSL" : True,
            "hostname" : "ubuntu-ext-17.cloudapp.net",
            "disabled" : False
        },
        {
            "disableSSL" : False,
            "hostname" : "sss-demo1.cloudapp.net",
            "disabled" : False
        },
        {
            "disableSSL" : False,
            "hostname" : "sss-demo2.cloudapp.net",
            "disabled" : False
        }
    ]
}

DEFAULT_SETTINGS_GUAC = {
    "webConsoleTool" : "guacamole",
    "isSteppingStone" : False,
    "disableSSL" : False,
    "hostname" : "localhost",
    "port" : 8080
}

DEFAULT_SETTINGS = DEFAULT_SETTINGS_SHELLINABOX_SSS
#DEFAULT_SETTINGS = DEFAULT_SETTINGS_GUAC

def install():
    hutil.do_parse_context('Install')
    try:
        script_file_path = os.path.realpath(sys.argv[0])
        os.system(' '.join(['python', script_file_path, '-web_console', '>/dev/null 2>&1 &']))
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded')
    except Exception, e:
        hutil.error('Failed to install the extension with error: %s, stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '0', 'Install Failed')

def enable():
    hutil.do_parse_context('Enable')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]\
                           ['handlerSettings'].get('protectedSettings')
        protect_settings = DEFAULT_SETTINGS
        web_console_handler.parse_settings(protect_settings)
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        web_console_handler.enable()
        time.sleep(10)
        messages = web_console_handler.get_web_console_uri()
        messages_str = ''
        if type(messages) is dict:
            for k,v in messages.items():
                messages_str += k + ': ' + v + '; '
        elif type(messages) is str:
            messages_str = messages
        hutil.do_exit(0, 'Enable', 'success', '0', messages_str.strip())
    except Exception, e:
        hutil.error('Failed to enable the extension with error: %s, stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '0', 'Enable Failed.')

def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall Succeeded')

def disable():
    hutil.do_parse_context('Disable')
    try:
        hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')
    except Exception, e:
        hutil.error('Failed to disable the extension with error: %s, stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Disable', 'error', '0', 'Disable Failed')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')

def install_web_console():
    hutil.do_parse_context('Install Web Console')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]\
                           ['handlerSettings'].get('protectedSettings')
        protect_settings = DEFAULT_SETTINGS
        web_console_handler.parse_settings(protect_settings)
        web_console_handler.install()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded')
    except Exception, e:
        hutil.error('Failed to install the extension with error: %s, stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '0', 'Install Failed')

# Main function is the only entrance to this extension handler
def main():
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." %(EXTENSION_SHORT_NAME))

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, EXTENSION_SHORT_NAME)

    global web_console_handler
    web_console_handler = WebConsoleHandler(hutil)

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
        elif re.match("^([-/]*)(web_console)", a):
            install_web_console()


if __name__ == '__main__':
    main()
