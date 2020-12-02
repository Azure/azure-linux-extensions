#
# Handler library for Linux IaaS
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


"""
JSON def:
HandlerEnvironment.json
[{
  "name": "ExampleHandlerLinux",
  "seqNo": "seqNo",
  "version": "1.0",
  "handlerEnvironment": {
    "logFolder": "<your log folder location>",
    "configFolder": "<your config folder location>",
    "statusFolder": "<your status folder location>",
    "heartbeatFile": "<your heartbeat file location>",
    
  }
}]

Example ./config/1.settings
"{"runtimeSettings":[{"handlerSettings":{"protectedSettingsCertThumbprint":"1BE9A13AA1321C7C515EF109746998BAB6D86FD1","protectedSettings":
"MIIByAYJKoZIhvcNAQcDoIIBuTCCAbUCAQAxggFxMIIBbQIBADBVMEExPzA9BgoJkiaJk/IsZAEZFi9XaW5kb3dzIEF6dXJlIFNlcnZpY2UgTWFuYWdlbWVudCBmb3IgR+nhc6VHQTQpCiiV2zANBgkqhkiG9w0BAQEFAASCAQCKr09QKMGhwYe+O4/a8td+vpB4eTR+BQso84cV5KCAnD6iUIMcSYTrn9aveY6v6ykRLEw8GRKfri2d6tvVDggUrBqDwIgzejGTlCstcMJItWa8Je8gHZVSDfoN80AEOTws9Fp+wNXAbSuMJNb8EnpkpvigAWU2v6pGLEFvSKC0MCjDTkjpjqciGMcbe/r85RG3Zo21HLl0xNOpjDs/qqikc/ri43Y76E/Xv1vBSHEGMFprPy/Hwo3PqZCnulcbVzNnaXN3qi/kxV897xGMPPC3IrO7Nc++AT9qRLFI0841JLcLTlnoVG1okPzK9w6ttksDQmKBSHt3mfYV+skqs+EOMDsGCSqGSIb3DQEHATAUBggqhkiG9w0DBwQITgu0Nu3iFPuAGD6/QzKdtrnCI5425fIUy7LtpXJGmpWDUA==","publicSettings":{"port":"3000"}}}]}"


Example HeartBeat
{
"version": 1.0,
    "heartbeat" : {
        "status": "ready",
        "code": 0,
        "Message": "Sample Handler running. Waiting for a new configuration from user."
    }
}
Example Status Report:
[{"version":"1.0","timestampUTC":"2014-05-29T04:20:13Z","status":{"name":"Chef Extension Handler","operation":"chef-client-run","status":"success","code":0,"formattedMessage":{"lang":"en-US","message":"Chef-client run success"}}}]

"""

import fnmatch
import glob
import os
import os.path
import re
import shutil
import string
import subprocess
import sys
import imp
import base64
import json
import tempfile
import time

from Common import *
from os.path import join
from Utils.WAAgentUtil import waagent
from waagent import LoggerInit
import logging
import logging.handlers

DateTimeFormat = "%Y-%m-%dT%H:%M:%SZ"

class HandlerContext:
    def __init__(self, name):
        self._name = name
        self._version = '0.0'
        return

class HandlerUtility:
    def __init__(self, log, error, short_name):
        self._log = log
        self._error = error
        self._short_name = short_name
        self.patching = None
        self.disk_util = None
        self.find_last_nonquery_operation = False
        self.config_archive_folder = '/var/lib/azure_disk_encryption_archive'
        self._context = HandlerContext(self._short_name)

    def _get_log_prefix(self):
        return '[%s-%s]' % (self._context._name, self._context._version)

    def _get_current_seq_no(self, config_folder):
        seq_no = -1
        cur_seq_no = -1
        freshest_time = None
        for subdir, dirs, files in os.walk(config_folder):
            for file in files:
                try:
                    if file.endswith('.settings'):
                        cur_seq_no = int(os.path.basename(file).split('.')[0])
                        if freshest_time == None:
                            freshest_time = os.path.getmtime(join(config_folder, file))
                            seq_no = cur_seq_no
                        else:
                            current_file_m_time = os.path.getmtime(join(config_folder, file))
                            if current_file_m_time > freshest_time:
                                freshest_time = current_file_m_time
                                seq_no = cur_seq_no
                except ValueError:
                    continue

        if seq_no < 0: 
            # guest agent is expected to provide at least one settings file to extension
            self.error("unable to get current sequence number from config folder")
                    
        return seq_no

    def get_last_seq(self):
        if os.path.isfile('mrseq'):
            seq = waagent.GetFileContents('mrseq')
            if seq:
                return int(seq)
        return -1

    def get_latest_seq(self):
        settings_files = glob.glob(os.path.join(self._context._config_dir, '*.settings'))
        settings_files = [os.path.basename(f) for f in settings_files]
        seq_nums = [int(re.findall(r'(\d+)\.settings', f)[0]) for f in settings_files]

        if seq_nums: 
            return max(seq_nums) 
        else:  
            # guest agent is expected to provide at least one settings file to the extension
            self.log("unable to get latest sequence number from config folder")
            return -1

    def get_current_seq(self):
        return int(self._context._seq_no)

    def same_seq_as_last_run(self):
        return self.get_current_seq() == self.get_last_seq()

    def exit_if_same_seq(self, exit_status=None):
        current_seq = int(self._context._seq_no)
        last_seq = self.get_last_seq()
        if current_seq == last_seq:
            self.log("the sequence numbers are same, so skipping daemon"+
                     ", current=" +
                     str(current_seq) +
                     ", last=" +
                     str(last_seq))

            if exit_status:
                self.do_status_report(exit_status['operation'],
                                      exit_status['status'],
                                      exit_status['status_code'],
                                      exit_status['message'])

            sys.exit(0)

    def log(self, message):
        # write message to stderr for inclusion in QOS telemetry 
        sys.stderr.write(message)
        self._log(self._get_log_prefix() + ': ' + message)

    def error(self, message):
        # write message to stderr for inclusion in QOS telemetry 
        sys.stderr.write(message)
        self._error(self._get_log_prefix() + ': ' + message)

    def _parse_config(self, config_txt):
        # pre : config_txt is a text string containing JSON configuration settings 
        # post: handlerSettings is initialized with these settings and the config 
        #       object is returned.  If an error occurs, None is returned. 
        if not config_txt:
            self.error('empty config, nothing to parse')
            return None

        config = None
        try:
            config = json.loads(config_txt)
        except:
            self.error('invalid config, could not parse: ' + str(config_txt))

        if config:
            handlerSettings = config['runtimeSettings'][0]['handlerSettings']

            # skip unnecessary decryption of protected settings for query status 
            # operations, to avoid timeouts in case of multiple settings files
            if handlerSettings.has_key('publicSettings'):
                ps = handlerSettings.get('publicSettings')
                op = ps.get(CommonVariables.EncryptionEncryptionOperationKey)
                if op == CommonVariables.QueryEncryptionStatus:
                    return config
            
            if handlerSettings.has_key('protectedSettings') and \
                    handlerSettings.has_key("protectedSettingsCertThumbprint") and \
                    handlerSettings['protectedSettings'] is not None and \
                    handlerSettings["protectedSettingsCertThumbprint"] is not None:
                thumb = handlerSettings['protectedSettingsCertThumbprint']
                cert = waagent.LibDir + '/' + thumb + '.crt'
                pkey = waagent.LibDir + '/' + thumb + '.prv'
                f = tempfile.NamedTemporaryFile(delete=False)
                f.close()
                waagent.SetFileContents(f.name, config['runtimeSettings'][0]['handlerSettings']['protectedSettings'])
                cleartxt = None
                cleartxt = waagent.RunGetOutput(self.patching.base64_path + " -d " + f.name + " | " + self.patching.openssl_path + " smime  -inform DER -decrypt -recip " + cert + "  -inkey " + pkey)[1]
                if cleartxt == None:
                    self.error("OpenSSh decode error using thumbprint " + thumb)
                    self.do_exit(1, self.operation,'error','1', self.operation + ' Failed')
                jctxt = ''
                try:
                    jctxt = json.loads(cleartxt)
                except:
                    self.error('JSON exception loading protected settings')
                handlerSettings['protectedSettings'] = jctxt
        return config

    def do_parse_context(self, operation):
        self.operation = operation
        _context = self.try_parse_context()
        if not _context:
            self.log("no settings file found")

            self.do_exit(0,
                         'QueryEncryptionStatus',
                         CommonVariables.extension_success_status,
                         str(CommonVariables.success),
                         'No operation found, find_last_nonquery_operation={0}'.format(self.find_last_nonquery_operation))

        return _context

    def is_valid_nonquery(self, settings_file_path):
        # note: the nonquery operations list includes update and disable 
        nonquery_ops = [ CommonVariables.EnableEncryption, CommonVariables.EnableEncryptionFormat, CommonVariables.EnableEncryptionFormatAll, CommonVariables.UpdateEncryptionSettings, CommonVariables.DisableEncryption ] 

        if settings_file_path and os.path.exists(settings_file_path):
            # open file and look for presence of nonquery operation 
            config_txt = waagent.GetFileContents(settings_file_path)
            config_obj = self._parse_config(config_txt)
            public_settings_str = config_obj['runtimeSettings'][0]['handlerSettings'].get('publicSettings')

            # if not json already, load string as json 
            if isinstance(public_settings_str, basestring):
                public_settings = json.loads(public_settings_str)
            else:
                public_settings = public_settings_str

            operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
            if operation and (operation in nonquery_ops):
                return True

        # invalid input, or not recognized as a valid nonquery operation 
        return False


    def get_last_nonquery_config_path(self):
        # pre: internal self._context._config_dir and _seq_no, _settings_file must be set prior to call
        # post: returns path to last nonquery settings file in current config, archived folder, or None
        
        # validate that internal preconditions are satisfied and internal variables are initialized
        if self._context._seq_no < 0:
            self.error("current context sequence number must be initialized and non-negative")
        if not self._context._config_dir or not os.path.isdir(self._context._config_dir):
            self.error("current context config dir must be initialized and point to a path that exists")
        if not self._context._settings_file or not os.path.exists(self._context._settings_file):
            self.error("current context settings file variable must be initialized and point to a file that exists")

        # check timestamp of pointer to last archived settings file 
        curr_path = self._context._settings_file
        last_path = os.path.join(self.config_archive_folder, "lnq.settings")
        
        # if an archived nonquery settings file exists, use it if no current settings file exists, or it is newer than current settings
        if os.path.exists(last_path) and ((not os.path.exists(curr_path)) or (os.path.exists(curr_path) and (os.stat(last_path).st_mtime > os.stat(curr_path).st_mtime))):
            return last_path
        else:
            # reverse iterate through numbered settings files in config dir
            # and return path to the first nonquery settings file found
            for i in range(self._context._seq_no,-1,-1):
                curr_path = os.path.join(self._context._config_dir, str(i) + '.settings')
                if self.is_valid_nonquery(curr_path):                    
                    return curr_path
            
            # nothing was found in the current config settings, check the archived settings
            if os.path.exists(last_path):
                return last_path
            else:
                if os.path.exists(self.config_archive_folder):                        
                    # walk through any archived [n].settings files found in archived settings folder 
                    # sorted by reverse timestamp (processing newest to oldest) until a nonquery settings file found 
                    files = sorted(os.listdir(self.config_archive_folder), key=os.path.getctime, reverse=True)
                    for f in files:
                        curr_path = os.path.join(self._context._config_dir, f)
                        # TODO: check that file name matches the [n].settings format
                        if self.is_valid_nonquery(curr_path):
                            # found, copy to last_nonquery_settings in archived settings
                            return curr_path

        # unable to find any nonquery settings file 
        return None 
        
    def get_last_config(self, nonquery):
        # precondition:  self._context._config_dir, self._context._seq_no are already set and valid 
        # postcondition: a configuration object from the last configuration settings file is returned 
        # if nonquery flag is true, search for the last settings file that was not a query status operation
        # if nonquery is false, return the current settings file 
        if nonquery:
            last_config_path = self.get_last_nonquery_config_path()
        else:
            # retrieve the settings file corresponding to the current sequence number 
            last_config_path = os.path.join(self._context._config_dir, str(self._context._seq_no) + '.settings')

        # if not found, attempt to fall back to an archived settings file
        if not os.path.isfile(last_config_path):
            self.log('settings file not found, checking for archived settings')
            last_config_path = os.path.join(self.config_archive_folder, "lnq.settings")
            if not os.path.isfile(last_config_path):
                self.error('archived settings file not found, unable to get last config')
                return None
            
        # settings file was found, parse config and return config object 
        config_txt = waagent.GetFileContents(last_config_path)
        if not config_txt:
            self.error('configuration settings empty, unable to get last config')
            return None
            
        config_obj = self._parse_config(config_txt)
        if not config_obj:
            self.error('failed to parse configuration settings, unable to get last config')
            return None  
        else:
            return config_obj

    def get_handler_env(self):
        # load environment variables from HandlerEnvironment.json 
        # according to spec, it is always in the ./ directory
        #self.log('cwd is ' + os.path.realpath(os.path.curdir))
        handler_env_file = './HandlerEnvironment.json'
        if not os.path.isfile(handler_env_file):
            self.error("Unable to locate " + handler_env_file)
            return None
        handler_env_json_str = waagent.GetFileContents(handler_env_file)

        if handler_env_json_str == None :
            self.error("Unable to read " + handler_env_file)
        try:
            handler_env = json.loads(handler_env_json_str)
        except:
            pass

        if handler_env == None :
            # TODO - treat this as a telemetry error indicating an agent bug, as this file should always be available and readable 
            self.log("JSON error processing " + str(handler_env_file))
            return None
        if type(handler_env) == list:
            handler_env = handler_env[0]
        return handler_env

    def try_parse_context(self):        
        # precondition: agent is in a properly running state with at least one settings file in config folder
        #               any archived settings from prior instances of the extension were saved to archive folder
        # postcondition: context variables initialized to reflect current handler environment and prior call history 
                
        # initialize handler environment context variables
        handler_env = self.get_handler_env()
        self._context._name = handler_env['name']
        self._context._version = str(handler_env['version'])
        self._context._config_dir = handler_env['handlerEnvironment']['configFolder']
        self._context._log_dir = handler_env['handlerEnvironment']['logFolder']
        self._context._log_file = os.path.join(handler_env['handlerEnvironment']['logFolder'],'extension.log')
        self._change_log_file()
        self._context._status_dir = handler_env['handlerEnvironment']['statusFolder']
        self._context._heartbeat_file = handler_env['handlerEnvironment']['heartbeatFile']

        # initialize the current sequence number corresponding to settings files in config folder
        self._context._seq_no = self._get_current_seq_no(self._context._config_dir)
        self._context._settings_file = os.path.join(self._context._config_dir, str(self._context._seq_no) + '.settings')
        
        # get a config object corresponding to the last settings file, skipping QueryEncryptionStatus settings 
        # files when find_last_nonquery_operation is True, falling back to archived settings if necessary
        # note - in the case of nonquery settings file retrieval, when preceded by one or more query settings 
        # file that are more recent, the config object will not match the active settings file or sequence number
        self._context._config = self.get_last_config(self.find_last_nonquery_operation)

        return self._context

    def _change_log_file(self):
        #self.log("Change log file to " + self._context._log_file)
        LoggerInit(self._context._log_file,'/dev/stdout')
        self._log = waagent.Log
        self._error = waagent.Error

    def save_seq(self):
        self.set_last_seq(self._context._seq_no)
        self.log("set most recent sequence number to " + str(self._context._seq_no))

    def set_last_seq(self, seq):
        waagent.SetFileContents('mrseq', str(seq))

    def redo_last_status(self):
        latest_sequence_num = self.get_latest_seq()
        if (latest_sequence_num > 0):
            latest_seq = str(latest_sequence_num)
            self._context._status_file = os.path.join(self._context._status_dir, latest_seq + '.status')

            previous_seq = str(latest_sequence_num - 1)
            previous_status_file = os.path.join(self._context._status_dir, previous_seq + '.status')

            shutil.copy2(previous_status_file, self._context._status_file)
            self.log("[StatusReport ({0})] Copied {1} to {2}".format(latest_seq, previous_status_file, self._context._status_file))
        else: 
            self.log("unable to redo last status, no prior status found")

    def redo_current_status(self):
        stat_rept = waagent.GetFileContents(self._context._status_file)
        stat = json.loads(stat_rept)

        self.do_status_report(stat[0]["status"]["operation"],
                              stat[0]["status"]["status"],
                              stat[0]["status"]["code"],
                              stat[0]["status"]["formattedMessage"]["message"])

    def do_status_report(self, operation, status, status_code, message):
        latest_seq_num = self.get_latest_seq()
        if (latest_seq_num >= 0): 
            latest_seq = str(self.get_latest_seq())
        else:
            self.log("sequence number could not be derived from settings files, using 0.status")
            latest_seq = "0"

        self._context._status_file = os.path.join(self._context._status_dir, latest_seq + '.status')

        if message is None:
            message = ""

        message = filter(lambda c: c in string.printable, message)
        message = message.encode('ascii', 'ignore')

        self.log("[StatusReport ({0})] op: {1}".format(latest_seq, operation))
        self.log("[StatusReport ({0})] status: {1}".format(latest_seq, status))
        self.log("[StatusReport ({0})] code: {1}".format(latest_seq, status_code))
        self.log("[StatusReport ({0})] msg: {1}".format(latest_seq, message))

        tstamp = time.strftime(DateTimeFormat, time.gmtime())
        stat = [{
            "version" : self._context._version,
            "timestampUTC" : tstamp,
            "status" : {
                "name" : self._context._name,
                "operation" : operation,
                "status" : status,
                "code" : status_code,
                "formattedMessage" : {
                    "lang" : "en-US",
                    "message" : message
                }
            }
        }]

        if self.disk_util:
            encryption_status = self.disk_util.get_encryption_status()

            encryption_status_dict = json.loads(encryption_status)
            self.log("[StatusReport ({0})] substatus : OS : {1}  Data : {2}".format(latest_seq, encryption_status_dict['os'], encryption_status_dict['data']))

            substat = [{
                "name" : self._context._name,
                "operation" : operation,
                "status" : status,
                "code" : status_code,
                "formattedMessage" : {
                    "lang" : "en-US",
                    "message" : encryption_status
                }
            }]

            stat[0]["status"]["substatus"] = substat

            if "VMRestartPending" in encryption_status:
                stat[0]["status"]["formattedMessage"]["message"] = "OS disk successfully encrypted, please reboot the VM"

        stat_rept = json.dumps(stat)
        # rename all other status files, or the WALA would report the wrong
        # status file.
        # because the wala choose the status file with the highest sequence
        # number to report.
        if self._context._status_file:
            with open(self._context._status_file,'w+') as f:
                f.write(stat_rept)

    def backup_settings_status_file(self, _seq_no):
        self.log("current seq no is " + _seq_no)
        for subdir, dirs, files in os.walk(self._context._config_dir):
            for file in files:
                try:
                    if file.endswith('.settings') and file != (_seq_no + ".settings"):
                        new_file_name = file.replace(".","_")
                        os.rename(join(self._context._config_dir, file), join(self._context._config_dir, new_file_name))
                except:
                    self.log("failed to rename the settings file.")

    def do_exit(self, exit_code, operation, status, code, message):
        try:
            self.do_status_report(operation, status, code, message)
        except Exception as e:
            self.log("Can't update status: " + str(e))
        if message:
            # Remove newline character so that msg is printed in one line
            strip_msg = message.replace('\n', ' ')
            self.log("Exited with message {0}".format(strip_msg))
        sys.exit(exit_code)

    def get_handler_settings(self):
        return self._context._config['runtimeSettings'][0]['handlerSettings']

    def get_protected_settings(self):
        return self.get_handler_settings().get('protectedSettings')

    def get_public_settings(self):
        return self.get_handler_settings().get('publicSettings')

    def archive_old_configs(self):
        if not os.path.exists(self.config_archive_folder):
            os.makedirs(self.config_archive_folder)

        # only persist latest nonquery settings file to archived settings 
        # and prevent the accumulation of large numbers of obsolete files 
        src = self.get_last_nonquery_config_path()
        if src:
            dest = os.path.join(self.config_archive_folder, 'lnq.settings')
            if src != dest: 
                shutil.copy2(src,dest)
