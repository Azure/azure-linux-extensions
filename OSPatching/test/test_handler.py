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
import json
import unittest

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

sys.path.append('..')
from patch import *
from FakePatching import FakePatching


# Global variables definition
ExtensionShortName = 'OSPatching'

contents = waagent.GetFileContents('default.settings')
protect_settings = json.loads(contents)
status_file = '/var/lib/waagent/Microsoft.OSTCExtensions.OSPatchingForLinuxTest-1.0/status/3.status'

def install():
    hutil.do_parse_context('Install')
    try:
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        MyPatching.install()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded')
    except Exception, e:
        hutil.error("Failed to install the extension with error: %s, \
                     stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '0', 'Install Failed')

def enable():
    hutil.do_parse_context('Enable')
    try:
        MyPatching.parse_settings(protect_settings)
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        MyPatching.enable()
        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded.')
    except Exception, e:
        hutil.error("Failed to enable the extension with error: %s, \
                     stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '0', 'Enable Failed.')

def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall Succeeded')

def disable():
    hutil.do_parse_context('Disable')
    try:
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        MyPatching.disable()
        hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')
    except Exception, e:
        hutil.error("Failed to disable the extension with error: %s, \
                     stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Disable', 'error', '0', 'Disable Failed')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')

def download():
    hutil.do_parse_context('Download')
    try:
        MyPatching.parse_settings(protect_settings)
        MyPatching.download()
        hutil.do_exit(0,'Download','success','0', 'Download Succeeded')
    except Exception, e:
        hutil.error("Failed to download updates with error: %s, \
                     stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Download','error','0', 'Download Failed')

def patch():
    hutil.do_parse_context('Patch')
    try:
        MyPatching.parse_settings(protect_settings)
        MyPatching.patch()
        hutil.do_exit(0,'Patch','success','0', 'Patch Succeeded')
    except Exception, e:
        hutil.error("Failed to patch with error: %s, stack trace: %s"
                    %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Patch','error','0', 'Patch Failed')

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


class Test(unittest.TestCase):
    def setUp(self):
        waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
        waagent.Log("%s started to handle." %(ExtensionShortName))

        global hutil
        hutil = Util.HandlerUtility(waagent.Log, waagent.Error,
                                    ExtensionShortName)
        global MyPatching
        MyPatching = FakePatching(hutil)
        if MyPatching == None:
            sys.exit(1)

        try:
            os.remove('mrseq')
        except:
            pass

    def test_parse_settings(self):
        protect_settings = {
            "disabled" : "false",
            "stop" : "false",
            "rebootAfterPatch" : "Auto",
            "dayOfWeek" : "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday",
            "startTime" : "02:00",
            "category" : "ImportantAndRecommended",
            "installDuration" : "00:30"
        }
        MyPatching.parse_settings(protect_settings)
        self.assertFalse(MyPatching.disabled)
        self.assertFalse(MyPatching.stop)
        self.assertEqual(MyPatching.reboot_after_patch, "Auto")
        self.assertEqual(MyPatching.day_of_week, [7, 1, 2, 3, 4, 5, 6])
        self.assertEqual(MyPatching.category, "ImportantAndRecommended")
        import datetime
        self.assertEqual(MyPatching.start_time, datetime.datetime.strptime("02:00", '%H:%M'))

    def test_install(self):
        with self.assertRaises(SystemExit) as cm:
            install()
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Install"), 'success')

    def test_enable(self):
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Enable"), 'success')
        # TODO: check /etc/crontab

    def test_disable(self):
        with self.assertRaises(SystemExit) as cm:
            disable()
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Disable"), 'success')
        # TODO: check /etc/crontab

    def test_download(self):
        with self.assertRaises(SystemExit) as cm:
            download()
        self.assertEqual(cm.exception.code, 0)

    def test_patch(self):
        with self.assertRaises(SystemExit) as cm:
            patch()
        self.assertEqual(cm.exception.code, 0)

def get_status(operation, retkey='status'):
    contents = waagent.GetFileContents(status_file)
    status = json.loads(contents)[0]['status']
    if status['operation'] == operation:
        return status[retkey]
    return ''

def unit_test_main():
    unittest.main()

if __name__ == '__main__':
    #main()
    unit_test_main()
