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
#
# Requires Python 2.7+


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


import os
import sys
import imp
import base64
import json
import time
from utils.waagentutil import waagent
from waagent import LoggerInit

DateTimeFormat = "%Y-%m-%dT%H:%M:%SZ"

class HandlerContext:
    def __init__(self,name):
        self._name = name
        self._version = '0.0'
        return

class HandlerUtility:
    def __init__(self, log, error, short_name):
        self._log = log
        self._error = error
        self._short_name = short_name
        
    def _get_log_prefix(self):
        return '[%s-%s]' %(self._context._name, self._context._version)

    def _get_current_seq_no(self, config_folder):
        seq_no = -1
        for subdir, dirs, files in os.walk(config_folder):
            for file in files:
                try:
                    cur_seq_no = int(os.path.basename(file).split('.')[0])
                    if cur_seq_no > seq_no:
                        seq_no = cur_seq_no
                except ValueError:
                    continue
        return seq_no

    def log(self, message):
        self._log(self._get_log_prefix() + message)

    def error(self, message):
        self._error(self._get_log_prefix() + message)
        
    def do_parse_context(self,operation):
        self._context = HandlerContext(self._short_name)
        handler_env=None
        config=None
        ctxt=None
        code=0
        # get the HandlerEnvironment.json. According to the extension handler spec, it is always in the ./ directory
        self.log('cwd is ' + os.path.realpath(os.path.curdir))
        handler_env_file='./HandlerEnvironment.json'
        if not os.path.isfile(handler_env_file):
            self.error("Unable to locate " + handler_env_file)
            sys.exit(1)
        ctxt=waagent.GetFileContents(handler_env_file)
        if ctxt == None :
            self.error("Unable to read " + handler_env_file)
        try:
            handler_env=json.loads(ctxt)
        except:
            pass
        if handler_env == None :
            self.log("JSON error processing " + handler_env_file)
            sys.exit(1)
        if type(handler_env) == list:
            handler_env = handler_env[0]

        self._context._name = handler_env['name']
        self._context._version = str(handler_env['version'])
        self._context._config_dir=handler_env['handlerEnvironment']['configFolder']
        self._context._log_file= os.path.join(handler_env['handlerEnvironment']['logFolder'],'extension.log')
        self._change_log_file()
        self._context._status_dir=handler_env['handlerEnvironment']['statusFolder']
        self._context._heartbeat_file=handler_env['handlerEnvironment']['heartbeatFile']
        self._context._seq_no = self._get_current_seq_no(self._context._config_dir)
        if self._context._seq_no < 0:
            self.error("Unable to locate a .settings file!")
            sys.exit(1)
        self._context._seq_no = str(self._context._seq_no)
        self.log('sequence number is ' + self._context._seq_no)
        self._context._status_file= os.path.join(self._context._status_dir, self._context._seq_no +'.status')
        self._context._settings_file = os.path.join(self._context._config_dir, self._context._seq_no + '.settings')
        self.log("setting file path is" + self._context._settings_file)
        ctxt=None
        ctxt=waagent.GetFileContents(self._context._settings_file)
        if ctxt == None :
            self.error('Unable to read ' + self._context._settings_file + '. ')
            self.do_exit(
                    1,
                    operation,
                    'error',
                    '1', 
                    'Failed')
        self.log("JSON config: " + ctxt)
        config = None
        try:
            config=json.loads(ctxt)
        except:
            self.error('JSON exception decoding ' + ctxt)
        if config == None:
            self.error("JSON error processing " + settings_file)
        else:
            if config['runtimeSettings'][0]['handlerSettings'].has_key('protectedSettings'):
                thumb=config['runtimeSettings'][0]['handlerSettings']['protectedSettingsCertThumbprint']
                cert=waagent.LibDir+'/'+thumb+'.crt'
                pkey=waagent.LibDir+'/'+thumb+'.prv'
                waagent.SetFileContents('/tmp/kk',config['runtimeSettings'][0]['handlerSettings']['protectedSettings'])
                cleartxt=None
                cleartxt=waagent.RunGetOutput("base64 -d /tmp/kk | openssl smime  -inform DER -decrypt -recip " +  cert + "  -inkey " + pkey )[1]
                if cleartxt == None:
                    self.error("OpenSSh decode error using  thumbprint " + thumb )
                    do_exit(1,operation,'error','1', operation + ' Failed')
                jctxt=''
                try:
                    jctxt=json.loads(cleartxt)
                except:
                    self.error('JSON exception decoding ' + cleartxt)
                config['runtimeSettings'][0]['handlerSettings']['protectedSettings']=jctxt
                self.log('Config decoded correctly.')
            self._context._config = config
        return self._context

    def _change_log_file(self):
        self.log("Change log file to " + self._context._log_file)
        LoggerInit(self._context._log_file,'/dev/stdout')
        self._log = waagent.Log
        self._error = waagent.Error

    def exit_if_enabled(self):
        if(int(self._context._seq_no) <= self._get_most_recent_seq()):
            self.log("Current sequence number, " + self._context._seq_no + ", is not greater than the sequnce number of the most recent executed configuration. Exiting...")
            sys.exit(0)
        self._set_most_recent_seq(self._context._seq_no)
        self.log("set most recent sequence number to " + self._context._seq_no)

    def _get_most_recent_seq(self):
        seq = waagent.GetFileContents('mrseq')
        if(seq):
            return int(seq)
        return -1

    def _set_most_recent_seq(self,seq):
        waagent.SetFileContents('mrseq', str(seq))

    def do_status_report(self, operation, status, status_code, message):
        tstamp=time.strftime(DateTimeFormat, time.gmtime())
        stat_rept = '[{"version":"1.0","timestampUTC":"%s","status":{"name":"%s","operation":"%s","status":"%s","code":%s,"formattedMessage":{"lang":"en-US","message":"%s"}}}]' %(tstamp, self._context._name, operation, status, status_code, message)
        if self._context._status_file:
            with open(self._context._status_file,'w+') as f:
                f.write(stat_rept)

    def do_heartbeat_report(self, heartbeat_file,status,code,message):
        # heartbeat
        health_report='[{"version":"1.0","heartbeat":{"status":"' + status+ '","code":"'+ code + '","Message":"' + message + '"}}]'
        if waagent.SetFileContents(heartbeat_file,health_report) == None :
            self.error('Unable to wite heartbeat info to ' + heartbeat_file)

    def do_exit(self,exit_code,operation,status,code,message):
        self.do_status_report(operation, status,code,message)
        sys.exit(exit_code)

