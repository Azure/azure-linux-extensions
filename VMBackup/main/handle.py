#!/usr/bin/env python
#
# VM Backup extension
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
#

import array
import base64
import os
import os.path
import re
import json
import string
import subprocess
import sys
import imp
import time
import shlex
import traceback
import httplib
import xml.parsers.expat
import datetime
from os.path import join
from mounts import Mounts
from mounts import Mount
from fsfreezer import FsFreezer
from common import CommonVariables
from parameterparser import ParameterParser
from Utils import HandlerUtil
from urlparse import urlparse
from snapshotter import Snapshotter
from backuplogger import Backuplogger
from blobwriter import BlobWriter
from taskidentity import TaskIdentity

#Main function is the only entrence to this extension handler
def main():
    global backup_logger
    global hutil
    HandlerUtil.LoggerInit('/var/log/waagent.log','/dev/stdout')
    HandlerUtil.waagent.Log("%s started to handle." % (CommonVariables.extension_name)) 
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    backup_logger = Backuplogger(hutil)
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

def install():
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install','success','0', 'Install Succeeded')

def do_backup_status_report(operation, status, status_code, message, taskId, commandStartTimeUTCTicks, blobUri):
        backup_logger.log("{0},{1},{2},{3}".format(operation, status, status_code, message))
        DateTimeFormat = "%Y-%m-%dT%H:%M:%SZ"
        tstamp = time.strftime(DateTimeFormat, time.gmtime())
        stat = [{
            "version" : hutil._context._version,
            "timestampUTC" : tstamp,
            "status" : {
                "name" : hutil._context._name,
                "operation" : operation,
                "status" : status,
                "code" : status_code,
                "taskId":taskId,
                "commandStartTimeUTCTicks":commandStartTimeUTCTicks,
                "formattedMessage" : {
                    "lang" : "en-US",
                    "message" : message
                }
            }
        }]
        status_report_msg = json.dumps(stat)
        blobWriter = BlobWriter(hutil)
        blobWriter.WriteBlob(status_report_msg,blobUri)

def exit_with_commit_log(error_msg, para_parser):
    backup_logger.log(error_msg, False, 'Error')
    if(para_parser is not None and para_parser.logsBlobUri is not None):
        backup_logger.commit(para_parser.logsBlobUri)
    sys.exit(0)

def convert_time(utcTicks):
    return datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds = utcTicks / 10)

def enable():
    freezer = FsFreezer(backup_logger)
    unfreeze_result = None
    snapshot_result = None
    freeze_result = None
    global_error_result = None
    para_parser = None
    run_result = 1
    error_msg = ''
    run_status = None
    # precheck
    freeze_called = False
    try:
        hutil.do_parse_context('Enable')

        # we need to freeze the file system first
        backup_logger.log('starting to enable', True)

        """
        protectedSettings is the privateConfig passed from Powershell.
        WATCHOUT that, the _context_config are using the most freshest timestamp.
        if the time sync is alive, this should be right.
        """
        protected_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
        para_parser = ParameterParser(protected_settings, public_settings)
        utcTicksLong = long(para_parser.commandStartTimeUTCTicks)
        commandStartTime = convert_time(utcTicksLong)
        
        utcNow = datetime.datetime.utcnow()
        backup_logger.log('command start time is ' + str(commandStartTime) + " and utcNow is " + str(utcNow))
        timespan = utcNow - commandStartTime
        TWENTY_MINUTES = 20 * 60 # in seconds
        taskIdentity = TaskIdentity()
        currentTaskIdentity = taskIdentity.stored_identity()
        # handle the machine identity for the restoration scenario.
        backup_logger.log('timespan is ' + str(timespan))
        if(abs(timespan.total_seconds()) > TWENTY_MINUTES):
            error_msg = 'the call time stamp is out of date.'
            exit_with_commit_log(error_msg, para_parser)

        elif(para_parser.taskId == currentTaskIdentity):
            error_msg = 'the task id is already handled.'
            exit_with_commit_log(error_msg, para_parser)
        else:
            taskIdentity.save_identity(para_parser.taskId)
            commandToExecute = para_parser.commandToExecute
            #validate all the required parameter here
            if(commandToExecute.lower() == CommonVariables.iaas_install_command):
                backup_logger.log('install succeed.',True)
                run_status = 'success'
                error_msg = 'Install Succeeded'
                run_result = CommonVariables.success
                backup_logger.log(error_msg)
            elif(commandToExecute.lower() == CommonVariables.iaas_vmbackup_command):
                if(para_parser.backup_metadata is None or para_parser.public_config_obj is None or para_parser.private_config_obj is None):
                    run_result = CommonVariables.parameter_error
                    run_status = 'error'
                    error_msg = 'required field empty or not correct'
                    backup_logger.log(error_msg, False, 'Error')
                else:
                    backup_logger.log('commandToExecute is ' + commandToExecute, True)
                    """
                    make sure the log is not doing when the file system is freezed.
                    """
                    backup_logger.log('doing freeze now...', True)
                    freeze_called = True
                    freeze_result = freezer.freezeall()
                    backup_logger.log('freeze result ' + str(freeze_result))

                    # check whether we freeze succeed first?
                    if(freeze_result is not None and len(freeze_result.errors) > 0):
                        run_result = CommonVariables.error
                        run_status = 'error'
                        error_msg = 'Enable failed with error: ' + str(freeze_result)
                        backup_logger.log(error_msg, False, 'Warning')
                    else:
                        backup_logger.log('doing snapshot now...')
                        snap_shotter = Snapshotter(backup_logger)
                        snapshot_result = snap_shotter.snapshotall(para_parser)
                        backup_logger.log('snapshotall ends...')
                        if(snapshot_result is not None and len(snapshot_result.errors) > 0):
                            error_msg = 'snapshot result: ' + str(snapshot_result)
                            run_result = CommonVariables.error
                            run_status = 'error'
                            backup_logger.log(error_msg, False, 'Error')
                        else:
                            run_result = CommonVariables.success
                            run_status = 'success'
                            error_msg = 'Enable Succeeded'
                            backup_logger.log(error_msg)
            else:
                run_status = 'error'
                run_result = CommonVariables.parameter_error
                error_msg = 'command is not correct'
                backup_logger.log(error_msg, False, 'Error')
    except Exception as e:
        errMsg = 'Failed to enable the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
        backup_logger.log(errMsg, False, 'Error')
        global_error_result = e
    finally:
        backup_logger.log('doing unfreeze now...')
        if(freeze_called):
            unfreeze_result = freezer.unfreezeall()
            backup_logger.log('unfreeze result ' + str(unfreeze_result))
            if(unfreeze_result is not None and len(unfreeze_result.errors) > 0):
                error_msg += ('Enable Succeeded with error: ' + str(unfreeze_result.errors))
                backup_logger.log(error_msg, False, 'Warning')
            backup_logger.log('unfreeze ends...')

    if(para_parser is not None and para_parser.logsBlobUri is not None):
        backup_logger.commit(para_parser.logsBlobUri)
    """
    we do the final report here to get rid of the complex logic to handle the logging when file system be freezed issue.
    """
    if(global_error_result is not None):
        if(hasattr(global_error_result,'errno') and global_error_result.errno == 2):
            run_result = CommonVariables.error_12
        elif(para_parser is None):
            run_result = CommonVariables.parameter_error
        else:
            run_result = CommonVariables.error
        run_status = 'error'
        error_msg  += ('Enable failed.' + str(global_error_result))

    if(para_parser is not None and para_parser.statusBlobUri is not None):
        do_backup_status_report(operation='Enable',status = run_status,status_code=str(run_result),message=error_msg,taskId=para_parser.taskId,commandStartTimeUTCTicks=para_parser.commandStartTimeUTCTicks,blobUri=para_parser.statusBlobUri)

    hutil.do_exit(0, 'Enable', run_status, str(run_result), error_msg)

def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    hutil.do_parse_context('Disable')
    hutil.do_exit(0,'Disable','success','0', 'Disable Succeeded')

def update():
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')

if __name__ == '__main__' :
    main()

