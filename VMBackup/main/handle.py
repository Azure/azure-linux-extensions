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
import ConfigParser
from threading import Thread
from time import sleep
from os.path import join
from mounts import Mounts
from mounts import Mount
from patch import *
from fsfreezer import FsFreezer
from common import CommonVariables
from parameterparser import ParameterParser
from Utils import HandlerUtil
from urlparse import urlparse
from snapshotter import Snapshotter
from backuplogger import Backuplogger
from blobwriter import BlobWriter
from taskidentity import TaskIdentity
from MachineIdentity import MachineIdentity

#Main function is the only entrence to this extension handler

def main():
    global MyPatching,backup_logger,hutil,run_result,run_status,error_msg,freezer,freeze_result,unfreeze_result,snapshot_result,snapshot_done
    snapshot_done = False
    run_result = CommonVariables.success
    run_status = 'success'
    error_msg = ''
    freeze_result = None
    unfreeze_result = None
    snapshot_result = None
    HandlerUtil.LoggerInit('/var/log/waagent.log','/dev/stdout')
    HandlerUtil.waagent.Log("%s started to handle." % (CommonVariables.extension_name)) 
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    backup_logger = Backuplogger(hutil)
    MyPatching = GetMyPatching(logger = backup_logger)
    hutil.patching = MyPatching
    
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
        elif re.match("^([-/]*)(daemon)", a):
            daemon()

def install():
    global hutil
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install','success','0', 'Install Succeeded')

def timedelta_total_seconds(delta):
    if not hasattr(datetime.timedelta, 'total_seconds'):
        return delta.days * 86400 + delta.seconds
    else:
        return delta.total_seconds()

def do_backup_status_report(operation, status, status_code, message, taskId, commandStartTimeUTCTicks, blobUri):
    global backup_logger,hutil
    backup_logger.log(msg="{0},{1},{2},{3}".format(operation, status, status_code, message),local=True)
    time_delta = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    time_span = timedelta_total_seconds(time_delta) * 1000
    date_string = r'\/Date(' + str((int)(time_span)) + r')\/'
    date_place_holder = 'e2794170-c93d-4178-a8da-9bc7fd91ecc0'
    stat = [{
        "version" : hutil._context._version,
        "timestampUTC" : date_place_holder,
        "status" : {
            "name" : hutil._context._name,
            "operation" : operation,
            "status" : status,
            "code" : status_code,
            "taskId": taskId,
            "commandStartTimeUTCTicks":commandStartTimeUTCTicks,
            "formattedMessage" : {
                "lang" : "en-US",
                "message" : message
            }
        }
    }]
    status_report_msg = json.dumps(stat)
    status_report_msg = status_report_msg.replace(date_place_holder,date_string)
    blobWriter = BlobWriter(hutil)
    blobWriter.WriteBlob(status_report_msg,blobUri)
    return status_report_msg

def exit_with_commit_log(error_msg, para_parser):
    global backup_logger
    backup_logger.log(error_msg, True, 'Error')
    if(para_parser is not None and para_parser.logsBlobUri is not None and para_parser.logsBlobUri != ""):
        backup_logger.commit(para_parser.logsBlobUri)
    sys.exit(0)

def convert_time(utcTicks):
    return datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds = utcTicks / 10)

def snapshot():
    try:
        global backup_logger,run_result,run_status,error_msg,freezer,freeze_result,snapshot_result,snapshot_done,para_parser
        freeze_result = freezer.freezeall()
        backup_logger.log('T:S freeze result ' + str(freeze_result))
        if(freeze_result is not None and len(freeze_result.errors) > 0):
            run_result = CommonVariables.error
            run_status = 'error'
            error_msg = 'T:S Enable failed with error: ' + str(freeze_result)
            backup_logger.log(error_msg, False, 'Warning')
        else:
            backup_logger.log('T:S doing snapshot now...')
            snap_shotter = Snapshotter(backup_logger)
            snapshot_result = snap_shotter.snapshotall(para_parser)
            backup_logger.log('T:S snapshotall ends...')
            if(snapshot_result is not None and len(snapshot_result.errors) > 0):
                error_msg = 'T:S snapshot result: ' + str(snapshot_result)
                run_result = CommonVariables.error
                run_status = 'error'
                backup_logger.log(error_msg, False, 'Error')
            else:
                run_result = CommonVariables.success
                run_status = 'success'
                error_msg = 'Enable Succeeded'
                backup_logger.log("T:S " + error_msg)
    except Exception as e:
        errMsg = 'Failed to do the snapshot with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
        backup_logger.log(errMsg, False, 'Error')
    snapshot_done = True

def daemon():
    global MyPatching,backup_logger,hutil,run_result,run_status,error_msg,freezer,para_parser,snapshot_done
    #this is using the most recent file timestamp.
    hutil.do_parse_context('Executing')
    freezer = FsFreezer(patching= MyPatching, logger = backup_logger)
    global_error_result = None
    # precheck
    freeze_called = False

    configfile='/etc/azure/vmbackup.conf'
    thread_timeout=str(60)
    try:
        config = ConfigParser.ConfigParser()
        config.read(configfile)
        thread_timeout= config.get('SnapshotThread','timeout')
    except Exception as e:
        errMsg='cannot read config file or file not present'
        backup_logger.log(errMsg, False, 'Warning')
    backup_logger.log("final thread timeout" + thread_timeout, True)

    try:
        # we need to freeze the file system first
        backup_logger.log('starting to enable', True)

        # handle the restoring scenario.
        mi = MachineIdentity()
        stored_identity = mi.stored_identity()
        if(stored_identity is None):
            mi.save_identity()
        else:
            current_identity = mi.current_identity()
            if(current_identity != stored_identity):
                current_seq_no = -1
                backup_logger.log("machine identity not same, set current_seq_no to " + str(current_seq_no) + " " + str(stored_identity) + " " + str(current_identity), True)
                hutil.set_last_seq(current_seq_no)
                mi.save_identity()

        hutil.exit_if_same_seq()
        hutil.save_seq()

        """
        protectedSettings is the privateConfig passed from Powershell.
        WATCHOUT that, the _context_config are using the most freshest timestamp.
        if the time sync is alive, this should be right.
        """
        protected_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
        para_parser = ParameterParser(protected_settings, public_settings)

        if(para_parser.commandStartTimeUTCTicks is not None and para_parser.commandStartTimeUTCTicks != ""):
            utcTicksLong = long(para_parser.commandStartTimeUTCTicks)
            backup_logger.log('utcTicks in long format' + str(utcTicksLong), True)
            commandStartTime = convert_time(utcTicksLong)
            utcNow = datetime.datetime.utcnow()
            backup_logger.log('command start time is ' + str(commandStartTime) + " and utcNow is " + str(utcNow))
            timespan = utcNow - commandStartTime
            THIRTY_MINUTES = 30 * 60 # in seconds
            # handle the machine identity for the restoration scenario.
            total_span_in_seconds = timedelta_total_seconds(timespan)
            backup_logger.log('timespan is ' + str(timespan) + ' ' + str(total_span_in_seconds))
            if(abs(total_span_in_seconds) > THIRTY_MINUTES):
                error_msg = 'the call time stamp is out of date. so skip it.'
                exit_with_commit_log(error_msg, para_parser)

        if(para_parser.taskId is not None and para_parser.taskId != ""):
            taskIdentity = TaskIdentity()
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
                run_result = CommonVariables.error_parameter
                run_status = 'error'
                error_msg = 'required field empty or not correct'
                backup_logger.log(error_msg, False, 'Error')
            else:
                backup_logger.log('commandToExecute is ' + commandToExecute, True)
                """
                make sure the log is not doing when the file system is freezed.
                """
                temp_status= 'transitioning'
                temp_result=CommonVariables.success
                temp_msg='Transitioning state in extension'
                trans_report_msg = None
                if(para_parser is not None and para_parser.statusBlobUri is not None and para_parser.statusBlobUri != ""):
                    trans_report_msg = do_backup_status_report(operation='Enable',status=temp_status,\
                                    status_code=str(temp_result),\
                                    message=temp_msg,\
                                    taskId=para_parser.taskId,\
                                    commandStartTimeUTCTicks=para_parser.commandStartTimeUTCTicks,\
                                    blobUri=para_parser.statusBlobUri)
                    if(trans_report_msg is not None):
                        backup_logger.log("trans status report message:")
                        backup_logger.log(trans_report_msg)
                    else:
                        backup_logger.log("trans_report_msg is none")
                hutil.do_status_report('Enable', temp_status, str(temp_result), temp_msg)
                backup_logger.log('doing freeze now...', True)
                snapshot_thread = Thread(target = snapshot)
                start_time=datetime.datetime.utcnow()
                snapshot_thread.start()
                snapshot_thread.join(float(thread_timeout))
                if not snapshot_done:
                    run_result = CommonVariables.error
                    run_status = 'error'
                    error_msg = 'T:W Snapshot timeout'
                    backup_logger.log(error_msg, False, 'Warning')

                end_time=datetime.datetime.utcnow()
                time_taken=end_time-start_time
                backup_logger.log('total time taken..' + str(time_taken))
                
                for i in range(0,3):
                    unfreeze_result = freezer.unfreezeall()
                    backup_logger.log('unfreeze result ' + str(unfreeze_result))
                    if(unfreeze_result is not None):
                        if len(unfreeze_result.errors) > 0:
                            error_msg += ('unfreeze with error: ' + str(unfreeze_result.errors))
                            backup_logger.log(error_msg, False, 'Warning')
                        else:
                            backup_logger.log('unfreeze result is None')
                            break;
                backup_logger.log('unfreeze ends...')
                
        else:
            run_status = 'error'
            run_result = CommonVariables.error_parameter
            error_msg = 'command is not correct'
            backup_logger.log(error_msg, False, 'Error')
    except Exception as e:
        errMsg = 'Failed to enable the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
        backup_logger.log(errMsg, False, 'Error')
        global_error_result = e

    """
    we do the final report here to get rid of the complex logic to handle the logging when file system be freezed issue.
    """
    if(global_error_result is not None):
        if(hasattr(global_error_result,'errno') and global_error_result.errno == 2):
            run_result = CommonVariables.error_12
        elif(para_parser is None):
            run_result = CommonVariables.error_parameter
        else:
            run_result = CommonVariables.error
        run_status = 'error'
        error_msg  += ('Enable failed.' + str(global_error_result))
    status_report_msg = None
    if(para_parser is not None and para_parser.statusBlobUri is not None and para_parser.statusBlobUri != ""):
        status_report_msg = do_backup_status_report(operation='Enable',status=run_status,\
                                status_code=str(run_result),\
                                message=error_msg,\
                                taskId=para_parser.taskId,\
                                commandStartTimeUTCTicks=para_parser.commandStartTimeUTCTicks,\
                                blobUri=para_parser.statusBlobUri)
    if(status_report_msg is not None):
        backup_logger.log("status report message:")
        backup_logger.log(status_report_msg)
    else:
        backup_logger.log("status_report_msg is none")
    if(para_parser is not None and para_parser.logsBlobUri is not None and para_parser.logsBlobUri != ""):
        backup_logger.commit(para_parser.logsBlobUri)
    else:
        backup_logger.log("the logs blob uri is not there, so do not upload log.")
        backup_logger.commit_to_local()

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

def enable():
    hutil.do_parse_context('Enable')
    start_daemon();

def start_daemon():
    args = [os.path.join(os.getcwd(), __file__), "-daemon"]
    backup_logger.log("start_daemon with args: {0}".format(args), True)
    #This process will start a new background process by calling
    #    handle.py -daemon
    #to run the script and will exit itself immediatelly.

    #Redirect stdout and stderr to /dev/null.  Otherwise daemon process will
    #throw Broke pipe exeception when parent process exit.
    devnull = open(os.devnull, 'w')
    child = subprocess.Popen(args, stdout=devnull, stderr=devnull)

if __name__ == '__main__' :
    main()
