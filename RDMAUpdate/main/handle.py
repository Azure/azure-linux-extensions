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
from patch import *
from os.path import join
from Common import CommonVariables
from Utils import HandlerUtil
from urlparse import urlparse
from RDMALogger import RDMALogger
from CronUtil import *
from SecondStageMarkConfig import SecondStageMarkConfig


def main():
    global logger
    global hutil
    global MyPatching
    HandlerUtil.LoggerInit('/var/log/waagent.log','/dev/stdout')
    HandlerUtil.waagent.Log("%s started to handle." % (CommonVariables.extension_name)) 
    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    logger = RDMALogger(hutil)
    MyPatching = GetMyPatching(logger)
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
        elif re.match("^([-/]*)(rdmaupdate)", a):
            rdmaupdate()
        elif re.match("^([-/]*)(chkrdma)", a):
            chkrdma()

def chkrdma():
    hutil.do_parse_context('Executing')
    check_result = MyPatching.check_rdma()
    if(check_result == CommonVariables.UpToDate):
        hutil.do_exit(0, 'Enable','success','0', 'RDMA Driver up to date.')
    if(check_result == CommonVariables.OutOfDate):
        hutil.do_exit(0, 'Enable','success','0', 'RDMA Driver out of date.')
    if(check_result == CommonVariables.DriverVersionNotFound):
        hutil.do_exit(0, 'Enable','success','0', 'RDMA Driver not found.')
    if(check_result == CommonVariables.Unknown):
        hutil.do_exit(0, 'Enable','success','0', 'RDMA version not found.')

def rdmaupdate():
    hutil.do_parse_context('Executing')
    try:
        MyPatching.rdmaupdate()
        hutil.do_status_report('Enable','success','0', 'Enable Succeeded')
        MyPatching.reboot_machine()
    except Exception as e:
        logger.log("Failed to update with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        hutil.do_exit(0, 'Enable','success','0','enable failed, please take a look at the extension log.')

def start_daemon():
    args = [os.path.join(os.getcwd(), __file__), "-rdmaupdate"]
    logger.log("start_daemon with args:" + str(args))
    devnull = open(os.devnull, 'w')
    child = subprocess.Popen(args, stdout=devnull, stderr=devnull)

def enable():
    # do it one time when enabling.
    # config the cron job
    hutil.do_parse_context('Enable')
    secondStageMarkConfig = SecondStageMarkConfig()
    if(secondStageMarkConfig.IsMarked()):
        secondStageMarkConfig.ClearIt()
        start_daemon()
    else:
        hutil.exit_if_enabled()
        cronUtil = CronUtil(logger)
        cronUtil.check_update_cron_config()
        cronUtil.restart_cron()
        start_daemon()

def install():
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install','success','0', 'Install Succeeded')

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