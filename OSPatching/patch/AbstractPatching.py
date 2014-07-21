#!/usr/bin/python
#
# AbstractPatching is the base patching class of all the linux distros
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
import imp
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util


class AbstractPatching(object):
    """
    AbstractPatching defines a skeleton neccesary for a concrete Patching class.
    """
    def __init__(self, hutil):
        self.patched = []
        self.to_patch = []
        self.downloaded = []
        self.to_download = []

        self.download_duration = 3600

        self.crontab = '/etc/crontab'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'

        self.hutil = hutil

    def parse_settings(self, settings):
        disabled = settings.get('disabled')
        if disabled is None:
            self.hutil.log("WARNING: the value of option \"disabled\" not \
                            specified in configuration\n Set it False by default")
        self.disabled = True if disabled in ['True', 'true'] else False
        if not self.disabled:
            day_of_week = settings.get('dayOfWeek')
            if day_of_week is None:
                day_of_week = 'Everyday'
            day2num = {'Monday':1, 'Tuesday':2, 'Wednesday':3, 'Thursday':4, 'Friday':5, 'Saturday':6, 'Sunday':7}
            if 'Everyday' in day_of_week:
                self.day_of_week = range(1,8)
            else:
                self.day_of_week = [day2num[day] for day in day_of_week.split('|')]

            start_time = settings.get('startTime')
            if start_time is None:
                start_time = '03:00'
            self.start_time = datetime.datetime.strptime(start_time, '%H:%M')

            self.download_time = self.start_time - datetime.timedelta(seconds=self.download_duration)
            # Stop downloading 10s before patching
            self.download_duration -= 10

            install_duration = settings.get('installDuration')
            if install_duration is None:
                self.install_duration = 3600
            else:
                hr_min = install_duration.split(':')
                self.install_duration = int(hr_min[0]) * 3600 + int(hr_min[1]) * 60
            # 5 min for reboot
            self.install_duration -= 300

            category = settings.get('category')
            if category is None:
                self.category = ''
            else:
                self.category = category

    def set_download_cron(self):
        contents = waagent.GetFileContents(self.crontab)
        script_file_path = os.path.realpath(sys.argv[0])
        script_dir = os.path.dirname(script_file_path)
        script_file = os.path.basename(script_file_path)
        old_line_end = ' '.join([script_file, '-download'])
        if self.disabled:
            new_line = '\n'
        else:
            hr = str(self.download_time.hour)
            if self.download_time.day != self.start_time.day:
                dow = ','.join([str(day - 1) for day in self.day_of_week])
            else:
                dow = ','.join([str(day) for day in self.day_of_week])
            new_line = ' '.join(['\n0', hr, '* *', dow, 'root cd', script_dir, '&& python', script_file, '-download >/dev/null 2>&1\n'])
        waagent.ReplaceFileContentsAtomic(self.crontab, '\n'.join(filter(lambda a: a and (old_line_end not in a), waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def set_patch_cron(self):
        contents = waagent.GetFileContents(self.crontab)
        script_file_path = os.path.realpath(sys.argv[0])
        script_dir = os.path.dirname(script_file_path)
        script_file = os.path.basename(script_file_path)
        old_line_end = ' '.join([script_file, '-patch'])
        if self.disabled:
            new_line = '\n'
        else:
            hr = str(self.start_time.hour)
            dow = ','.join([str(day) for day in self.day_of_week])
            new_line = ' '.join(['\n0', hr, '* *', dow, 'root cd', script_dir, '&& python', script_file, '-patch >/dev/null 2>&1\n'])
        waagent.ReplaceFileContentsAtomic(self.crontab, "\n".join(filter(lambda a: a and (old_line_end not in a), waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def restart_cron(self):
        if self.disabled:
            return
        retcode,output = waagent.RunGetOutput(self.cron_restart_cmd)
        if retcode > 0:
            self.hutil.error(output)

    def install(self):
        pass

    def enable(self):
        self.set_download_cron()
        self.set_patch_cron()
        self.restart_cron()

    def disable(self):
        self.disabled = True
        self.enable()
