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

import os
import sys
import re
import time
import chardet
import tempfile
import urllib2
import urlparse
import shutil
import traceback
import logging
from azure.storage import BlobService
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
import json
import unittest
from patch import *
from FakePatching3 import FakePatching

sys.path.append('..')


# Global variables definition
ExtensionShortName = 'OSPatching'
DownloadDirectory = 'download'
idleTestScriptName = "idleTest.py"
healthyTestScriptName = "healthyTest.py"
handlerName = os.path.basename(sys.argv[0])
status_file = './status/0.status'
log_file = './extension.log'

settings_file = "default.settings"
with open(settings_file, "r") as f:
    settings_string = f.read()
settings = json.loads(settings_string)

def install():
    hutil.do_parse_context('Install')
    try:
        MyPatching.install()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded.')
    except Exception as e:
        hutil.log_and_syslog(logging.ERROR, "Failed to install the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '0', 'Install Failed.')

def enable():
    hutil.do_parse_context('Enable')
    try:
        MyPatching.parse_settings(settings)
        # Ensure the same configuration is executed only once
        hutil.exit_if_seq_smaller()
        oneoff = settings.get("oneoff")
        download_customized_vmstatustest()
        copy_vmstatustestscript(hutil.get_seq_no(), oneoff)
        MyPatching.enable()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded. Current Configuration: ' + current_config)
    except Exception as e:
        current_config = MyPatching.get_current_config()
        hutil.log_and_syslog(logging.ERROR, "Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
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
    except Exception as e:
        hutil.log_and_syslog(logging.ERROR, "Failed to disable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Disable', 'error', '0', 'Disable Failed.')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded.')

def download():
    hutil.do_parse_context('Download')
    try:
        MyPatching.parse_settings(settings)
        MyPatching.download()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0,'Enable','success','0', 'Download Succeeded. Current Configuation: ' + current_config)
    except Exception as e:
        current_config = MyPatching.get_current_config()
        hutil.log_and_syslog(logging.ERROR, "Failed to download updates with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Download Failed. Current Configuation: ' + current_config)

def patch():
    hutil.do_parse_context('Patch')
    try:
        MyPatching.parse_settings(settings)
        MyPatching.patch()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0,'Enable','success','0', 'Patch Succeeded. Current Configuation: ' + current_config)
    except Exception as e:
        current_config = MyPatching.get_current_config()
        hutil.log_and_syslog(logging.ERROR, "Failed to patch with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Patch Failed. Current Configuation: ' + current_config)

def oneoff():
    hutil.do_parse_context('Oneoff')
    try:
        MyPatching.parse_settings(settings)
        MyPatching.patch_one_off()
        current_config = MyPatching.get_current_config()
        hutil.do_exit(0,'Enable','success','0', 'Oneoff Patch Succeeded. Current Configuation: ' + current_config)
    except Exception as e:
        current_config = MyPatching.get_current_config()
        hutil.log_and_syslog(logging.ERROR, "Failed to one-off patch with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Oneoff Patch Failed. Current Configuation: ' + current_config)

def download_files(hutil):
    local = settings.get("vmStatusTest", dict()).get("local", "")
    if local.lower() == "true":
        local = True
    elif local.lower() == "false":
        local = False
    else:
        hutil.log_and_syslog(logging.WARNING, "The parameter \"local\" "
                  "is empty or invalid. Set it as False. Continue...")
        local = False
    idle_test_script = settings.get("vmStatusTest", dict()).get('idleTestScript')
    healthy_test_script = settings.get("vmStatusTest", dict()).get('healthyTestScript')

    if (not idle_test_script and not healthy_test_script):
        hutil.log_and_syslog(logging.WARNING, "The parameter \"idleTestScript\" and \"healthyTestScript\" "
                  "are both empty. Exit downloading VMStatusTest scripts...")
        return
    elif local:
        if (idle_test_script and idle_test_script.startswith("http")) or \
           (healthy_test_script and healthy_test_script.startswith("http")):
            hutil.log_and_syslog(logging.WARNING, "The parameter \"idleTestScript\" or \"healthyTestScript\" "
                  "should not be uri. Exit downloading VMStatusTest scripts...")
            return
    elif not local:
        if (idle_test_script and not idle_test_script.startswith("http")) or \
           (healthy_test_script and not healthy_test_script.startswith("http")):
            hutil.log_and_syslog(logging.WARNING, "The parameter \"idleTestScript\" or \"healthyTestScript\" "
                  "should be uri. Exit downloading VMStatusTest scripts...")
            return

    hutil.do_status_report('Downloading','transitioning', '0',
                           'Downloading VMStatusTest scripts...')

    vmStatusTestScripts = dict()
    vmStatusTestScripts[idle_test_script] = idleTestScriptName
    vmStatusTestScripts[healthy_test_script] = healthyTestScriptName

    if local:
        hutil.log_and_syslog(logging.INFO, "Saving VMStatusTest scripts from user's configurations...")
        for src,dst in vmStatusTestScripts.items():
            if not src:
                continue
            file_path = save_local_file(src, dst, hutil)
            preprocess_files(file_path, hutil)
        return

    storage_account_name = None
    storage_account_key = None
    if settings:
        storage_account_name = settings.get("storageAccountName", "").strip()
        storage_account_key = settings.get("storageAccountKey", "").strip()
    if storage_account_name and storage_account_key:
        hutil.log_and_syslog(logging.INFO, "Downloading VMStatusTest scripts from azure storage...")
        for src,dst in vmStatusTestScripts.items():
            if not src:
                continue
            file_path = download_blob(storage_account_name,
                                      storage_account_key,
                                      src,
                                      dst,
                                      hutil)
            preprocess_files(file_path, hutil)
    elif not(storage_account_name or storage_account_key):
        hutil.log_and_syslog(logging.INFO, "No azure storage account and key specified in protected "
                  "settings. Downloading VMStatusTest scripts from external links...")
        for src,dst in vmStatusTestScripts.items():
            if not src:
                continue
            file_path = download_external_file(src, dst, hutil)
            preprocess_files(file_path, hutil)
    else:
        #Storage account and key should appear in pairs
        error_msg = "Azure storage account or storage key is not provided"
        hutil.log_and_syslog(logging.ERROR, error_msg)
        raise ValueError(error_msg)

def download_blob(storage_account_name, storage_account_key,
                  blob_uri, dst, hutil):
    seqNo = hutil.get_seq_no()
    container_name = get_container_name_from_uri(blob_uri)
    blob_name = get_blob_name_from_uri(blob_uri)
    download_dir = prepare_download_dir(seqNo)
    download_path = os.path.join(download_dir, dst)
    #Guest agent already ensure the plugin is enabled one after another.
    #The blob download will not conflict.
    blob_service = BlobService(storage_account_name, storage_account_key)
    try:
        blob_service.get_blob_to_path(container_name, blob_name, download_path)
    except Exception as e:
        hutil.log_and_syslog(logging.ERROR, ("Failed to download blob with uri:{0} "
                     "with error {1}").format(blob_uri,e))
        raise
    return download_path

def download_external_file(uri, dst, hutil):
    seqNo = hutil.get_seq_no()
    download_dir = prepare_download_dir(seqNo)
    file_path = os.path.join(download_dir, dst)
    try:
        download_and_save_file(uri, file_path)
    except Exception as e:
        hutil.log_and_syslog(logging.ERROR, ("Failed to download external file with uri:{0} "
                     "with error {1}").format(uri, e))
        raise
    return file_path

def save_local_file(src, dst, hutil):
    seqNo = hutil.get_seq_no()
    download_dir = prepare_download_dir(seqNo)
    file_path = os.path.join(download_dir, dst)
    try:
        waagent.SetFileContents(file_path, src)
    except Exception as e:
        hutil.log_and_syslog(logging.ERROR, ("Failed to save file from user's configuration "
                     "with error {0}").format(e))
        raise
    return file_path

def preprocess_files(file_path, hutil):
    """
        Preprocess the text file. If it is a binary file, skip it.
    """
    is_text, code_type = is_text_file(file_path)
    if is_text:
        dos2unix(file_path)
        hutil.log_and_syslog(logging.INFO, "Converting text files from DOS to Unix formats: Done")
        if code_type in ['UTF-8', 'UTF-16LE', 'UTF-16BE']:
            remove_bom(file_path)
            hutil.log_and_syslog(logging.INFO, "Removing BOM: Done")

def is_text_file(file_path):
    with open(file_path, 'rb') as f:
        contents = f.read(512)
    return is_text(contents)

def is_text(contents):
    supported_encoding = ['ascii', 'UTF-8', 'UTF-16LE', 'UTF-16BE']
    code_type = chardet.detect(contents)['encoding']
    if code_type in supported_encoding:
        return True, code_type
    else:
        return False, code_type

def dos2unix(file_path):
    temp_file_path = tempfile.mkstemp()[1]
    f_temp = open(temp_file_path, 'wb')
    with open(file_path, 'rU') as f:
        contents = f.read()
    f_temp.write(contents)
    f_temp.close()
    shutil.move(temp_file_path, file_path)

def remove_bom(file_path):
    temp_file_path = tempfile.mkstemp()[1]
    f_temp = open(temp_file_path, 'wb')
    with open(file_path, 'rb') as f:
        contents = f.read()
    for encoding in ["utf-8-sig", "utf-16"]:
        try:
            f_temp.write(contents.decode(encoding).encode('utf-8'))
            break
        except UnicodeDecodeError:
            continue
    f_temp.close()
    shutil.move(temp_file_path, file_path)

def download_and_save_file(uri, file_path):
    src = urllib2.urlopen(uri)
    dest = open(file_path, 'wb')
    buf_size = 1024
    buf = src.read(buf_size)
    while(buf):
        dest.write(buf)
        buf = src.read(buf_size)

def prepare_download_dir(seqNo):
    download_dir_main = os.path.join(os.getcwd(), DownloadDirectory)
    create_directory_if_not_exists(download_dir_main)
    download_dir = os.path.join(download_dir_main, seqNo)
    create_directory_if_not_exists(download_dir)
    return download_dir

def create_directory_if_not_exists(directory):
    """create directory if no exists"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_path_from_uri(uriStr):
    uri = urlparse.urlparse(uriStr)
    return uri.path

def get_blob_name_from_uri(uri):
    return get_properties_from_uri(uri)['blob_name']

def get_container_name_from_uri(uri):
    return get_properties_from_uri(uri)['container_name']

def get_properties_from_uri(uri):
    path = get_path_from_uri(uri)
    if path.endswith('/'):
        path = path[:-1]
    if path[0] == '/':
        path = path[1:]
    first_sep = path.find('/')
    if first_sep == -1:
        hutil.log_and_syslog(logging.ERROR, "Failed to extract container, blob, from {}".format(path))
    blob_name = path[first_sep+1:]
    container_name = path[:first_sep]
    return {'blob_name': blob_name, 'container_name': container_name}

def download_customized_vmstatustest():
    maxRetry = 2
    for retry in range(0, maxRetry + 1):
        try:
            download_files(hutil)
            break
        except Exception:
            hutil.log_and_syslog(logging.ERROR, "Failed to download files, retry=" + str(retry) + ", maxRetry=" + str(maxRetry))
            if retry != maxRetry:
                hutil.log_and_syslog(logging.INFO, "Sleep 10 seconds")
                time.sleep(10)
            else:
                raise

def copy_vmstatustestscript(seqNo, oneoff):
    src_dir = prepare_download_dir(seqNo)
    for filename in (idleTestScriptName, healthyTestScriptName):
        src = os.path.join(src_dir, filename)
        if os.path.isfile(src):
            if oneoff is not None and oneoff.lower() == "true":
                dst = "oneoff"
            else:
                dst = "scheduled"
            dst = os.path.join(os.getcwd(), dst)
            shutil.copy(src, dst)

def delete_current_vmstatustestscript():
    for filename in (idleTestScriptName, healthyTestScriptName):
        current_vmstatustestscript = os.path.join(os.getcwd(), "patch/"+filename)
        if os.path.isfile(current_vmstatustestscript):
            os.remove(current_vmstatustestscript)

class Test(unittest.TestCase):
    def setUp(self):
        print('\n\n============================================================================================')
        waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
        waagent.Log("%s started to handle." %(ExtensionShortName))
        global hutil
        hutil = Util.HandlerUtility(waagent.Log, waagent.Error,
                                    ExtensionShortName)
        hutil.do_parse_context('TEST')

        global MyPatching
        MyPatching = FakePatching(hutil)
        if MyPatching is None:
            sys.exit(1)

        distro = DistInfo()[0]
        if 'centos' in distro or 'Oracle' in distro or 'redhat' in distro:
            MyPatching.cron_restart_cmd = 'service crond restart'

        try:
            os.remove('mrseq')
        except:
            pass

        waagent.SetFileContents(MyPatching.package_downloaded_path, '')
        waagent.SetFileContents(MyPatching.package_patched_path, '')

    def test_stop_between_download_and_stage1(self):
        print('test_stop_between_download_and_stage1')

        global settings
        current_time = time.time()
        settings = change_settings("startTime", time.strftime('%H:%M', time.localtime(current_time + 180)))
        settings = change_settings("category", "importantandrecommended")

        old_log_len = len(waagent.GetFileContents(log_file))
        delta_time = int(time.strftime('%S', time.localtime(current_time + 120)))
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)

        # set stop flag after downloaded 40 seconds
        time.sleep(160 - delta_time)
        os.remove('mrseq')
        settings = change_settings("stop", "true")
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(MyPatching.exists_stop_flag())

        # Make sure the total sleep time is greater than 180s
        time.sleep(20 + delta_time + 5 + 60)
        self.assertFalse(MyPatching.exists_stop_flag())
        download_list = get_patch_list(MyPatching.package_downloaded_path)
        self.assertEqual(download_list, ['a', 'b', 'c', 'd', 'e', '1', '2', '3', '4'])
        self.assertFalse(waagent.GetFileContents(MyPatching.package_patched_path))
        log_contents = waagent.GetFileContents(log_file)[old_log_len:]
        self.assertTrue('Installing patches is stopped/canceled' in log_contents)
        restore_settings()

    def test_stop_between_stage1_and_stage2(self):
        print 'test_stop_between_stage1_and_stage2'

        global settings
        current_time = time.time()
        settings = change_settings("startTime", time.strftime('%H:%M', time.localtime(current_time + 180)))
        settings = change_settings("category", "importantandrecommended")

        old_log_len = len(waagent.GetFileContents(log_file))
        delta_time = int(time.strftime('%S', time.localtime(current_time)))
        with self.assertRaises(SystemExit) as cm:
            enable()
        self.assertEqual(cm.exception.code, 0)

        # Set stop flag after patched 10 seconds
        # Meanwhile the extension is sleeping between stage 1 & 2
        time.sleep(180 - delta_time + 10)
        os.remove('mrseq')
        settings = change_settings("stop", "true")
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
        log_contents = waagent.GetFileContents(log_file)[old_log_len:]
        self.assertTrue("Installing patches (Category:" + MyPatching.category_all + ") is stopped/canceled" in log_contents)
        restore_settings()


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

def change_settings(key, value):
    with open(settings_file, "r") as f:
        settings_string = f.read()
        settings = json.loads(settings_string)
    with open(settings_file, "w") as f:
        settings[key] = value
        settings_string = json.dumps(settings)
        f.write(settings_string)
    return settings

def restore_settings():
    idleTestScriptLocal = """#!/usr/bin/python
    # Locally.
    def is_vm_idle():
        return True
    """

    healthyTestScriptLocal = """#!/usr/bin/python
    # Locally.
    def is_vm_healthy():
        return True
    """

    settings = {
        "disabled" : "false",
        "stop" : "false",
        "rebootAfterPatch" : "rebootifneed",
        "category" : "important",
        "installDuration" : "00:30",
        "oneoff" : "false",
        "intervalOfWeeks" : "1",
        "dayOfWeek" : "everyday",
        "startTime" : "03:00",
        "vmStatusTest" : {
            "local" : "true",
            "idleTestScript" : idleTestScriptLocal, #idleTestScriptStorage,
            "healthyTestScript" : healthyTestScriptLocal, #healthyTestScriptStorage
        },
        "storageAccountName" : "<TOCHANGE>",
        "storageAccountKey" : "<TOCHANGE>"
    }

    settings_string = json.dumps(settings)
    settings_file = "default.settings"
    with open(settings_file, "w") as f:
        f.write(settings_string)

def main():
    if len(sys.argv) == 1:
        unittest.main()
        return

    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." % ExtensionShortName)

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error,
                                ExtensionShortName)
    hutil.do_parse_context('TEST')
    global MyPatching
    MyPatching = FakePatching(hutil)

    if MyPatching is None:
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
