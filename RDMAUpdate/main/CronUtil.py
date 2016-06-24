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

import os
import os.path
import sys
from Utils import HandlerUtil
from CommandExecuter import CommandExecuter
from Common import CommonVariables


class CronUtil(object):
    """description of class"""
    def __init__(self,logger):
        self.logger = logger
        self.crontab = '/etc/crontab'
        self.cron_restart_cmd = 'service cron restart'

    def check_update_cron_config(self):
        script_file_path = os.path.realpath(sys.argv[0])
        script_dir = os.path.dirname(script_file_path)
        script_file = os.path.basename(script_file_path)
        old_line_end = ' '.join([script_file, '-chkrdma'])

        new_line = ' '.join(['\n0 0 * * *', 'root cd', script_dir + "/..", '&& python main/handle.py -chkrdma >/dev/null 2>&1\n'])

        HandlerUtil.waagent.ReplaceFileContentsAtomic(self.crontab, \
            '\n'.join(filter(lambda a: a and (old_line_end not in a), HandlerUtil.waagent.GetFileContents(self.crontab).split('\n')))+ new_line)
    
    def restart_cron(self):
        commandExecuter = CommandExecuter(self.logger)
        returnCode = commandExecuter.Execute(self.cron_restart_cmd)
        if(returnCode != CommonVariables.process_success):
            self.logger.log(msg="",level=CommonVariables.ErrorLevel)
