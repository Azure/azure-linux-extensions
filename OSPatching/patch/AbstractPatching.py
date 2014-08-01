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
        self.hutil = hutil

        self.patched = []
        self.to_patch = []
        self.downloaded = []

        self.disabled = None
        self.stop = None
        self.reboot_after_patch = None
        self.day_of_week = None
        self.start_time = None
        self.download_time = None
        self.install_duration = None
        self.download_duration = None
        self.patch_now = None
        self.category = None

        self.crontab = '/etc/crontab'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'

        self.package_downloaded_path = os.path.join(waagent.LibDir, 'package.downloaded')
        self.package_patched_path = os.path.join(waagent.LibDir, 'package.patched')
        self.stop_flag_path = os.path.join(waagent.LibDir, 'StopOSPatching')

        self.category_required = 'Important'
        self.category_all = 'ImportantAndRecommended'

        self.gap_between_stage = 60

    def parse_settings(self, settings):
        disabled = settings.get('disabled')
        if disabled is None:
            self.hutil.log("WARNING: the value of option \"disabled\" not \
                            specified in configuration\n Set it False by default")
        self.disabled = True if disabled in ['True', 'true'] else False
        if self.disabled:
            return

        stop = settings.get('stop')
        self.stop = True if stop in ['True', 'true'] else False

        reboot_after_patch = settings.get('rebootAfterPatch')
        if reboot_after_patch is None or reboot_after_patch == '':
            self.reboot_after_patch = 'Auto'
        else:
            self.reboot_after_patch = reboot_after_patch

        start_time = settings.get('startTime')
        if start_time is None or start_time == '':
            self.patch_now = True
        else:
            self.patch_now = False
            self.start_time = datetime.datetime.strptime(start_time, '%H:%M')
            self.download_duration = 3600
            self.download_time = self.start_time - datetime.timedelta(seconds=self.download_duration)
 
            day_of_week = settings.get('dayOfWeek')
            if day_of_week is None or day_of_week == '':
                self.hutil.log('dayOfWeek defaults to Everyday')
                day_of_week = 'Everyday'
            day2num = {'Monday':1, 'Tuesday':2, 'Wednesday':3, 'Thursday':4, 'Friday':5, 'Saturday':6, 'Sunday':7}
            if 'Everyday' in day_of_week:
                self.day_of_week = range(1,8)
            else:
                self.day_of_week = [day2num[day] for day in day_of_week.split('|')]

        install_duration = settings.get('installDuration')
        if install_duration is None or install_duration == '':
            self.hutil.log('install_duration defaults to 3600s')
            self.install_duration = 3600
        else:
            hr_min = install_duration.split(':')
            self.install_duration = int(hr_min[0]) * 3600 + int(hr_min[1]) * 60
        # 5 min for reboot
        self.install_duration -= 300

        category = settings.get('category')
        if category is None or category == '':
            self.hutil.log('category defaults to ' + self.category_all)
            self.category = self.category_all
        else:
            self.category = category

    def install(self):
        pass

    def enable(self):
        if self.stop:
            self.stop_download()
            self.create_stop_flag()
            return
        self.delete_stop_flag()
        if not self.disabled and self.patch_now:
            self.patch_one_off()
        else:
            self.set_download_cron()
            self.set_patch_cron()
            self.restart_cron()

    def disable(self):
        self.disabled = True
        self.enable()

    def stop_download(self):
        '''
        kill the process of downloading and its subprocess.
        return code:
            0   - There are no downloading process to stop
            100 - The downloading process is stopped
        '''
        script_file_path = os.path.realpath(sys.argv[0])
        script_file = os.path.basename(script_file_path)
        retcode, output = waagent.RunGetOutput('ps -ef | grep "' + script_file + ' -download" | grep -v grep | grep -v sh | awk \'{print $2}\'')
        if retcode > 0:
            self.hutil.error(output)
        if output != '':
            retcode, output2 = waagent.RunGetOutput("ps -ef | awk '{if($3==" + output.strip() + ") {print $2}}'")
            if retcode > 0:
                self.hutil.error(output2)
            if output2 != '':
                waagent.Run('kill -15 ' + output2.strip())
            waagent.Run('kill -15 ' + output.strip())
            return 100
        return 0

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
            minute = str(self.download_time.minute)
            if self.download_time.day != self.start_time.day:
                dow = ','.join([str(day - 1) for day in self.day_of_week])
            else:
                dow = ','.join([str(day) for day in self.day_of_week])
            new_line = ' '.join(['\n' + minute, hr, '* *', dow, 'root cd', script_dir, '&& python', script_file, '-download >/dev/null 2>&1\n'])
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
            minute = str(self.start_time.minute)
            dow = ','.join([str(day) for day in self.day_of_week])
            new_line = ' '.join(['\n' + minute, hr, '* *', dow, 'root cd', script_dir, '&& python', script_file, '-patch >/dev/null 2>&1\n'])
        waagent.ReplaceFileContentsAtomic(self.crontab, "\n".join(filter(lambda a: a and (old_line_end not in a), waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def restart_cron(self):
        retcode,output = waagent.RunGetOutput(self.cron_restart_cmd)
        if retcode > 0:
            self.hutil.error(output)

    def download(self):
        if self.exists_stop_flag():
            self.hutil.log("Downloading patches is stopped/canceled")
            return

        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')

        # Installing security patches is mandatory
        self._download(self.category_required)
        if self.category == self.category_all:
            self._download(self.category_all)

    def _download(self, category):
        self.hutil.log("Start to check&download patches (Category:" + category + ")")
        downloadlist = self.check(category)
        self.hutil.log("download list: " + ' '.join(downloadlist))
        for pkg_name in downloadlist:
            if pkg_name in self.downloaded:
                continue
            retcode = self.download_package(pkg_name)
            if retcode != 0:
                self.hutil.error("Failed to download the package: " + pkg_name)
                continue
            self.downloaded.append(pkg_name)
            self.hutil.log("Package " + pkg_name + " is downloaded.")
            waagent.AppendFileContents(self.package_downloaded_path, pkg_name + ' ' + category + '\n')

    def patch(self):
        if self.exists_stop_flag():
            self.hutil.log("Installing patches is stopped/canceled")
            self.delete_stop_flag()
            return

        retcode = self.stop_download()
        if retcode == 100:
            self.hutil.error("Download time exceeded. The pending package will be \
                                downloaded in the next cycle")

        global start_patch_time
        start_patch_time = time.time()

        patchlist = self.get_pkg_to_patch(self.category_required)
        self._patch(self.category_required, patchlist)
        if not self.exists_stop_flag():
            self.hutil.log("Going to sleep for " + str(self.gap_between_stage) + "s")
            time.sleep(self.gap_between_stage)
            patchlist = self.get_pkg_to_patch(self.category_all)
            self._patch(self.category_all, patchlist)
        else:
            self.hutil.log("Installing patches (Category:" + self.category_all + ") is stopped/canceled")

        self.delete_stop_flag()
        #self.report()
        self.reboot_if_required()

    def _patch(self, category, patchlist):
        if self.exists_stop_flag():
            self.hutil.log("Installing patches (Category:" + category + ") is stopped/canceled")
            return
        self.hutil.log("Start to install " + str(len(patchlist)) +" patches (Category:" + category + ")")
        self.hutil.log("patch list: " + ' '.join(patchlist))
        for pkg_name in patchlist:
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log("Patching time exceeded. The pending package will be \
                                patched in the next cycle")
                break
            retcode = self.patch_package(pkg_name)
            if retcode != 0:
                self.hutil.error("Failed to patch the package:" + pkg_name)
                continue
            self.patched.append(pkg_name)
            self.hutil.log("Package " + pkg_name + " is patched.")
            waagent.AppendFileContents(self.package_patched_path, pkg_name + ' ' + category + '\n')

    def patch_one_off(self):
        """
        Called when startTime is empty string, which means a on-demand patch.
        """
        global start_patch_time
        start_patch_time = time.time()

        self.hutil.log("Going to patch one-off")
        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')

        patchlist = self.check(self.category_required)
        self._patch(self.category_required, patchlist)
        if not self.exists_stop_flag():
            self.hutil.log("Going to sleep for " + str(self.gap_between_stage) + "s")
            time.sleep(self.gap_between_stage)
            patchlist = self.check(self.category_all)
            self._patch(self.category_all, patchlist)
        else:
            self.hutil.log("Installing patches (Category:" + self.category_all + ") is stopped/canceled")
        shutil.copy2(self.package_patched_path, self.package_downloaded_path)

        self.delete_stop_flag()
        #self.report()
        self.reboot_if_required()

    def reboot_if_required(self):
        """
        In auto mode, a reboot should be only necessary when kernel has been upgraded.
        """
        if self.reboot_after_patch == 'NotRequired':
            return
        if self.reboot_after_patch == 'Required' or (self.reboot_after_patch == 'Auto' and self.check_reboot()):
            self.hutil.log("System going to reboot...")
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")

    def create_stop_flag(self):
        waagent.SetFileContents(self.stop_flag_path, '')

    def delete_stop_flag(self):
        if self.exists_stop_flag():
            os.remove(self.stop_flag_path)

    def exists_stop_flag(self):
        if os.path.isfile(self.stop_flag_path):
            return True
        else:
            return False

    def get_pkg_to_patch(self, category):
        patchlist = [line.split()[0] for line in waagent.GetFileContents(self.package_downloaded_path).split('\n') if line.endswith(category)]
        return patchlist
