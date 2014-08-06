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
import time

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

sys.path.append('..')
from patch import *
from FakePatching2 import FakePatching


# Global variables definition
ExtensionShortName = 'OSPatching'

contents = waagent.GetFileContents('default.settings')
protect_settings = json.loads(contents)
status_file = '/var/lib/waagent/Microsoft.OSTCExtensions.OSPatchingForLinuxTest-1.0/status/3.status'
log_file = '/var/log/azure/Microsoft.OSTCExtensions.OSPatchingForLinuxTest/1.0/extension.log'

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


class Test(unittest.TestCase):
    def setUp(self):
        print '\n\n============================================================================================'
        waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
        waagent.Log("%s started to handle." %(ExtensionShortName))

        global protect_settings
        protect_settings = json.loads(contents)
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

        waagent.SetFileContents(MyPatching.package_downloaded_path, '')
        waagent.SetFileContents(MyPatching.package_patched_path, '')

    def test_download_time_exceed(self):
        '''
        Manually add time.sleep(11) in download_package() 
        check package.downloaded and package.patched
        '''
        print 'test_download_time_exceed'

        old_log_len = len(waagent.GetFileContents(log_file))
        current_time = time.time()
        protect_settings['startTime'] = time.strftime('%H:%M', time.localtime(current_time + 180))
        MyPatching.download_duration = 60

        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)
        time.sleep(180 + 10)

        all_download_list = get_patch_list(MyPatching.package_downloaded_path)
        self.assertTrue(set(all_download_list) == set(['a', 'b', 'c', 'd', 'e']))
        # Check extension.log
        log_contents = waagent.GetFileContents(log_file)[old_log_len:]
        self.assertTrue('Download time exceeded' in log_contents)

    def test_stop_while_download(self):
        """
        Manually add time.sleep(11) in download_package()
        """
        print 'test_stop_while_download'

        old_log_len = len(waagent.GetFileContents(log_file))
        current_time = time.time()
        protect_settings['startTime'] = time.strftime('%H:%M', time.localtime(current_time + 180))
        delta_time = int(time.strftime('%S', time.localtime(current_time + 120)))
        MyPatching.download_duration = 60
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)

        # set stop flag after downloaded 40 seconds
        time.sleep(160 - delta_time)
        os.remove('mrseq')
        protect_settings['stop'] = 'true'
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(MyPatching.exists_stop_flag())

        # Make sure the total sleep time is greater than 180s
        time.sleep(20 + delta_time + 5)
        self.assertFalse(MyPatching.exists_stop_flag())
        download_list = get_patch_list(MyPatching.package_downloaded_path)
        self.assertEqual(download_list, ['a', 'b', 'c'])
        self.assertFalse(waagent.GetFileContents(MyPatching.package_patched_path))
        # Check extension.log
        log_contents = waagent.GetFileContents(log_file)[old_log_len:]
        self.assertTrue('Installing patches is stopped/canceled' in log_contents)


def get_patch_list(file_path, category = None):
    content = waagent.GetFileContents(file_path)
    if category != None:
        result = [line.split()[0] for line in content.split('\n') if line.endswith(category)]
    else:
        result = [line.split()[0] for line in content.split('\n') if ' ' in line]
    return result
    

def get_status(operation, retkey='status'):
    contents = waagent.GetFileContents(status_file)
    status = json.loads(contents)[0]['status']
    if status['operation'] == operation:
        return status[retkey]
    return ''

# Main function is the only entrance to this extension handler
def main():
    if len(sys.argv) == 1:
        unittest.main()
        return

    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName))

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error,
                                ExtensionShortName)
    global MyPatching
    MyPatching = FakePatching(hutil)

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


if __name__ == '__main__':
    main()
