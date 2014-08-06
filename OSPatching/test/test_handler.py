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

    def test_parse_settings(self):
        print 'test_parse_settings'

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
        """
        Each Distro has different dependencies for OSPatching Extension.
        It is MANUAL to check whether they are installed or not.
        Ubuntu        : update-notifier-common
        CentOS/Oracle : yum-downloadonly
                        yum-plugin-security
        SuSE          : None
        """
        print 'test_install'

        with self.assertRaises(SystemExit) as cm:
            install()

        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Install"), 'success')

    def test_enable(self):
        print 'test_enable'

        with self.assertRaises(SystemExit) as cm:
            enable()

        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Enable"), 'success')
        download_cmd = 'python test_handler.py -download'
        patch_cmd = 'python test_handler.py -patch'
        crontab_content = waagent.GetFileContents('/etc/crontab')
        self.assertTrue(download_cmd in crontab_content)
        self.assertTrue(patch_cmd in crontab_content)

    def test_disable(self):
        print 'test_disable'

        with self.assertRaises(SystemExit) as cm:
            disable()

        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Disable"), 'success')
        download_cmd = 'python test_handler.py -download'
        patch_cmd = 'python test_handler.py -patch'
        crontab_content = waagent.GetFileContents('/etc/crontab')
        self.assertTrue(download_cmd not in crontab_content)
        self.assertTrue(patch_cmd not in crontab_content)
        
    def test_download(self):
        """
        Check file package.downloaded after download
        """
        print 'test_download'

        with self.assertRaises(SystemExit) as cm:
            download()

        self.assertEqual(cm.exception.code, 0)
        download_content = waagent.GetFileContents(MyPatching.package_downloaded_path)
        security_download_list = get_patch_list(MyPatching.package_downloaded_path, 'Important')
        self.assertTrue(set(security_download_list) == set(MyPatching.security_download_list))
        all_download_list = get_patch_list(MyPatching.package_downloaded_path)
        self.assertTrue(set(all_download_list) == set(MyPatching.all_download_list))

    def test_download_security(self):
        """
        check file package.downloaded after download
        """
        print 'test_download_security'
        protect_settings['category'] = 'Important'

        with self.assertRaises(SystemExit) as cm:
            download()

        self.assertEqual(cm.exception.code, 0)
        security_download_list = get_patch_list(MyPatching.package_downloaded_path, 'Important')
        self.assertTrue(set(security_download_list) == set(MyPatching.security_download_list))
        all_download_list = get_patch_list(MyPatching.package_downloaded_path)
        self.assertTrue(set(all_download_list) == set(MyPatching.security_download_list))

    def _test_download_time_exceed(self):
        '''
        Manually add time.sleep(11) in download_package() 
        check package.downloaded and package.patched
        '''
        print 'test_download_time_exceed'

        current_time = time.time()
        protect_settings['startTime'] = time.strftime('%H:%M', time.localtime(current_time + 180))
        MyPatching.download_duration = 60

        all_download_list = get_patch_list(MyPatching.package_downloaded_path)
        with self.assertRaises(SystemExit) as cm:
            enable()

        self.assertEqual(cm.exception.code, 0)
        time.sleep(180)
        self.assertTrue(all_download_list == ['a', 'b', 'c', 'd', 'e'])
        # Check extension.log

    def test_patch(self):
        '''
        check file package.patched when patch successful
        '''
        print 'test_patch'
        
        with self.assertRaises(SystemExit) as cm:
            download()
        self.assertEqual(cm.exception.code, 0)
        with self.assertRaises(SystemExit) as cm:
            patch()
        self.assertEqual(cm.exception.code, 0)

        download_content = waagent.GetFileContents(MyPatching.package_downloaded_path)
        patch_content = waagent.GetFileContents(MyPatching.package_patched_path)
        self.assertEqual(download_content, patch_content)
        

    def test_patch_failed(self):
        '''
        check file package.patched when patch fail
        '''
        print 'test_patch_failed'

        def patch_package(self):
            return 1
        MyPatching.patch_package = patch_package

        with self.assertRaises(SystemExit) as cm:
            download()
        self.assertEqual(cm.exception.code, 0)
        with self.assertRaises(SystemExit) as cm:
            patch()

        self.assertEqual(cm.exception.code, 0)
        patch_content = waagent.GetFileContents(MyPatching.package_patched_path)
        self.assertFalse(patch_content)
        
    def test_patch_one_off(self):
        '''
        check package.downloaded and package.patched when patch_one_off successful
        '''
        print 'test_patch_one_off'
        protect_settings['startTime'] = ''

        with self.assertRaises(SystemExit) as cm:
            enable()

        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(get_status("Enable"), 'success')
        security_download_list = get_patch_list(MyPatching.package_downloaded_path, 'Important')
        self.assertTrue(set(security_download_list) == set(MyPatching.security_download_list))
        all_download_list = get_patch_list(MyPatching.package_patched_path)
        self.assertTrue(set(all_download_list) == set(MyPatching.all_download_list))
        download_content = waagent.GetFileContents(MyPatching.package_downloaded_path)
        patch_content = waagent.GetFileContents(MyPatching.package_patched_path)
        self.assertEqual(patch_content, download_content)

    def test_patch_time_exceed(self):
        '''
        check package.patched when patch time exceed
        '''
        print 'test_patch_time_exceed'

        def patch_package(self):
            time.sleep(11)
            return 0
        MyPatching.patch_package = patch_package
        # 5 minutes reserved for reboot
        protect_settings['installDuration'] = '00:06'
        
        with self.assertRaises(SystemExit) as cm:
            download()
        self.assertEqual(cm.exception.code, 0)
        with self.assertRaises(SystemExit) as cm:
            patch()
        self.assertEqual(cm.exception.code, 0)

        patch_list = get_patch_list(MyPatching.package_patched_path)
        self.assertEqual(patch_list, ['a', 'b', 'c', 'd', 'e', '1'])

    def test_stop_before_download(self):
        '''
        check stop flag before download and after patch
        '''
        print 'test_stop_before_download'

        current_time = time.time()
        protect_settings['startTime'] = time.strftime('%H:%M', time.localtime(current_time + 180))
        MyPatching.download_duration = 60
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)

        os.remove('mrseq')
        protect_settings['stop'] = 'true'
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(MyPatching.exists_stop_flag())

        time.sleep(180 + 5)
        self.assertFalse(MyPatching.exists_stop_flag())
        self.assertFalse(waagent.GetFileContents(MyPatching.package_downloaded_path))
        self.assertFalse(waagent.GetFileContents(MyPatching.package_patched_path))

    def _test_stop_while_download(self):
        """
        Manually add time.sleep(11) in download_package()
        """
        print 'test_stop_while_download'

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

    def test_stop_between_download_and_stage1(self):
        print 'test_stop_between_download_and_stage1'

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
        self.assertEqual(download_list, ['a', 'b', 'c', 'd', 'e', '1', '2', '3', '4'])
        self.assertFalse(waagent.GetFileContents(MyPatching.package_patched_path))

    def _test_stop_between_stage1_and_stage2(self):
        """
        Manually add MyPathing.gap_between_stage = 20
        """
        print 'test_stop_between_stage1_and_stage2'

        current_time = time.time()
        protect_settings['startTime'] = time.strftime('%H:%M', time.localtime(current_time + 180))
        delta_time = int(time.strftime('%S', time.localtime(current_time + 120)))
        MyPatching.download_duration = 60
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)

        # Set stop flag after patched 10 seconds
        # Meanwhile the extension is sleeping between stage 1 & 2
        time.sleep(190 - delta_time)
        os.remove('mrseq')
        protect_settings['stop'] = 'true'
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(MyPatching.exists_stop_flag())

        # The patching (stage 1 & 2) has ended
        time.sleep(20)
        self.assertFalse(MyPatching.exists_stop_flag())
        download_list = get_patch_list(MyPatching.package_downloaded_path)
        self.assertEqual(download_list, ['a', 'b', 'c', 'd', 'e', '1', '2', '3', '4'])
        patch_list = get_patch_list(MyPatching.package_patched_path)
        self.assertEqual(patch_list, ['a', 'b', 'c', 'd', 'e'])


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
