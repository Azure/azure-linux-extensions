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
import logging

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

# Global variables definition
ExtensionShortName = 'OSPatching'
VMStatusTestTemplate = False

try:
    from VMStatusTestUserDefined import VMStatusTest
except:
    from VMStatusTestDefault import VMStatusTest
    VMStatusTestTemplate = True

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
        self.interval_of_weeks = None
        self.day_of_week = None
        self.start_time = None
        self.download_time = None
        self.install_duration = None
        self.patch_now = None
        self.category = None
        self.download_duration = 3600
        self.gap_between_stage = 60

        self.crontab = '/etc/crontab'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'

        self.package_downloaded_path = os.path.join(waagent.LibDir, 'package.downloaded')
        self.package_patched_path = os.path.join(waagent.LibDir, 'package.patched')
        self.stop_flag_path = os.path.join(waagent.LibDir, 'StopOSPatching')
        self.history_scheduled = os.path.join(os.path.dirname(sys.argv[0]), 'history/scheduled')

        self.category_required = 'Important'
        self.category_all = 'ImportantAndRecommended'

        self.check_idle = True
        self.check_healthy = True

        self.current_config_list = list()

        # Reboot Requirements
        self.reboot_required = False
        self.open_deleted_files_before = list()
        self.open_deleted_files_after = list()
        self.needs_restart = list()

    def parse_settings(self, settings):
        disabled = settings.get('disabled')
        if disabled is None:
            msg = "The value of option \"disabled\" not \
                  specified in configuration\n Set it False by default"
            self.hutil.log_and_syslog(logging.WARNING, msg)

        self.disabled = True if disabled in ['True', 'true'] else False
        self.current_config_list.append('disabled=' + str(self.disabled))
        if self.disabled:
            msg = "The extension " + ExtensionShortName+ "is disabled"
            self.hutil.log_and_syslog(logging.INFO, msg)
            return

        stop = settings.get('stop')
        self.stop = True if stop in ['True', 'true'] else False
        self.current_config_list.append('stop=' + str(self.stop))

        reboot_after_patch = settings.get('rebootAfterPatch')
        if reboot_after_patch is None or reboot_after_patch == '':
            self.reboot_after_patch = 'Auto'
        else:
            self.reboot_after_patch = reboot_after_patch
        self.current_config_list.append('rebootAfterPatch=' + self.reboot_after_patch)

        start_time = settings.get('startTime')
        if start_time is None or start_time == '':
            msg = 'startTime defaults to Now'
            self.hutil.log_and_syslog(logging.INFO, msg)
            self.patch_now = True
            self.current_config_list.append('startTime=Now')
        else:
            self.patch_now = False
            self.current_config_list.append('startTime=' + start_time)            
            self.start_time = datetime.datetime.strptime(start_time, '%H:%M')
            self.download_time = self.start_time - datetime.timedelta(seconds=self.download_duration)
 
            day_of_week = settings.get('dayOfWeek')
            if day_of_week is None or day_of_week == '':
                msg = 'dayOfWeek defaults to Everyday'
                self.hutil.log_and_syslog(logging.INFO, msg)
                day_of_week = 'Everyday'
            self.current_config_list.append('dayOfWeek=' + day_of_week)
            day2num = {'Monday':1, 'Tuesday':2, 'Wednesday':3, 'Thursday':4, 'Friday':5, 'Saturday':6, 'Sunday':7}
            if 'Everyday' in day_of_week:
                self.day_of_week = range(1,8)
            else:
                self.day_of_week = [day2num[day] for day in day_of_week.split('|')]

            interval_of_weeks = settings.get('intervalOfWeeks')
            if interval_of_weeks is None or interval_of_weeks == '':
                self.interval_of_weeks = '1'
            else:
                self.interval_of_weeks = interval_of_weeks
            self.current_config_list.append('intervalOfWeeks=' + str(self.interval_of_weeks))

        install_duration = settings.get('installDuration')
        if install_duration is None or install_duration == '':
            msg = 'install_duration defaults to 3600s'
            self.hutil.log_and_syslog(logging.INFO, msg)
            self.install_duration = 3600
        else:
            hr_min = install_duration.split(':')
            self.install_duration = int(hr_min[0]) * 3600 + int(hr_min[1]) * 60
        self.current_config_list.append('installDuration=' + str(self.install_duration))
        # 5 min for reboot
        self.install_duration -= 300

        category = settings.get('category')
        if category is None or category == '':
            msg = 'category defaults to ' + self.category_all
            self.hutil.log_and_syslog(logging.INFO, msg)
            self.category = self.category_all
        else:
            self.category = category
        self.current_config_list.append('category=' + self.category)

        check_idle = settings.get('vmStatusTest', dict()).get('checkIdle')
        if (check_idle is None or check_idle == ''):
            # Skip idle check by default in "Patch Now" mode
            if self.patch_now:
                self.check_idle = False
        else:
            if check_idle.lower() == 'true':
                self.check_idle = True
            elif check_idle.lower() == 'false':
                self.check_idle = False
            else:
                msg = 'checkIdle parameter is invalid'
                self.hutil.log_and_syslog(logging.ERROR, msg)
        self.current_config_list.append('checkIdle=' + str(self.check_idle))

        check_healthy = settings.get('VMStatusTest', dict()).get('checkHealthy')
        if not (check_healthy is None or check_healthy == ''):
            if check_healthy.lower() == 'true':
                self.check_healthy = True
            elif check_healthy.lower() == 'false':
                self.check_healthy = False
            else:
                msg = 'checkHealthy parameter is invalid'
                self.hutil.log_and_syslog(logging.ERROR, msg)
        self.current_config_list.append('checkHealthy=' + str(self.check_healthy))
        msg = self.get_current_config()
        self.hutil.log_and_syslog(logging.INFO, msg)

    def install(self):
        pass

    def enable(self):
        if self.stop:
            self.stop_download()
            self.create_stop_flag()
            return
        self.delete_stop_flag()
        if not self.disabled and self.patch_now:
            script_file_path = os.path.realpath(sys.argv[0])
            os.system(' '.join(['python', script_file_path, '-oneoff', '>/dev/null 2>&1 &']))
        else:
            waagent.SetFileContents(self.history_scheduled, '')
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
            100  - There are no downloading process to stop
            0    - The downloading process is stopped
        '''
        script_file_path = os.path.realpath(sys.argv[0])
        script_file = os.path.basename(script_file_path)
        retcode, output = waagent.RunGetOutput('ps -ef | grep "' + script_file + ' -download" | grep -v grep | grep -v sh | awk \'{print $2}\'')
        if retcode > 0:
            self.hutil.log_and_syslog(logging.ERROR, output)
        if output != '':
            retcode, output2 = waagent.RunGetOutput("ps -ef | awk '{if($3==" + output.strip() + ") {print $2}}'")
            if retcode > 0:
                self.hutil.log_and_syslog(logging.ERROR, output2)
            if output2 != '':
                waagent.Run('kill -9 ' + output2.strip())
            waagent.Run('kill -9 ' + output.strip())
            return 0
        return 100

    def set_download_cron(self):
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
            new_line = ' '.join(['\n' + minute, hr, '* *', dow, 'root cd', script_dir, '&& python check.py', self.interval_of_weeks, '&& python', script_file, '-download > /dev/null 2>&1\n'])
        waagent.ReplaceFileContentsAtomic(self.crontab, '\n'.join(filter(lambda a: a and (old_line_end not in a), waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def set_patch_cron(self):
        script_file_path = os.path.realpath(sys.argv[0])
        script_dir = os.path.dirname(script_file_path)
        script_file = os.path.basename(script_file_path)
        old_line_end = ' '.join([script_file, '-patch'])
        if self.disabled:
            new_line = '\n'
        else:
            hr = str(self.start_time.hour)
            minute = str(self.start_time.minute)
            minute_cleanup = str(self.start_time.minute + 1)
            dow = ','.join([str(day) for day in self.day_of_week])
            new_line = ' '.join(['\n' + minute, hr, '* *', dow, 'root cd', script_dir, '&& python check.py', self.interval_of_weeks, '&& python', script_file, '-patch >/dev/null 2>&1\n'])
            new_line += ' '.join([minute_cleanup, hr, '* *', dow, 'root rm -f', self.stop_flag_path, '\n'])
        waagent.ReplaceFileContentsAtomic(self.crontab, "\n".join(filter(lambda a: a and (old_line_end not in a) and (self.stop_flag_path not in a), waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def restart_cron(self):
        retcode,output = waagent.RunGetOutput(self.cron_restart_cmd)
        if retcode > 0:
            self.hutil.log_and_syslog(logging.ERROR, output)

    def download(self):
        self.is_template()
        if self.check_idle:
            if VMStatusTest.is_vm_idle():
                msg = "Checking the VM is idle: True"
            else:
                msg = "Checking the VM is idle: False. Downloading is skipped."
            self.hutil.log_and_syslog(logging.INFO, msg)
            return
        else:
            msg = "Skipped VM idle checking"
            self.hutil.log_and_syslog(logging.INFO, msg)

        if self.exists_stop_flag():
            self.hutil.log_and_syslog(logging.INFO, "Downloading patches is stopped/canceled")
            return

        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')

        # Installing security patches is mandatory
        self._download(self.category_required)
        if self.category == self.category_all:
            self._download(self.category_all)

    def _download(self, category):
        self.hutil.log_and_syslog(logging.INFO, "Start to check&download patches (Category:" + category + ")")
        retcode, downloadlist = self.check(category)
        if retcode > 0:
            self.hutil.log_and_syslog(logging.ERROR, "Failed to check valid upgrades")
            sys.exit(1)
        if 'walinuxagent' in downloadlist:
            downloadlist.remove('walinuxagent')
        if not downloadlist:
            self.hutil.log_and_syslog(logging.INFO, "No packages are available for update.")
            return
        self.hutil.log_and_syslog(logging.INFO, "There are " + str(len(downloadlist)) + " packages to upgrade.")
        self.hutil.log_and_syslog(logging.INFO, "Download list: " + ' '.join(downloadlist))
        for pkg_name in downloadlist:
            if pkg_name in self.downloaded:
                continue
            retcode = self.download_package(pkg_name)
            if retcode != 0:
                self.hutil.log_and_syslog(logging.ERROR, "Failed to download the package: " + pkg_name)
                continue
            self.downloaded.append(pkg_name)
            self.hutil.log_and_syslog(logging.INFO, "Package " + pkg_name + " is downloaded.")
            waagent.AppendFileContents(self.package_downloaded_path, pkg_name + ' ' + category + '\n')

    def patch(self):
        if self.check_idle:
            if VMStatusTest.is_vm_idle():
                msg = "Checking the VM is idle: True"
            else:
                msg = "Checking the VM is idle: False. Patching is skipped."
            self.hutil.log_and_syslog(logging.INFO, msg)
            return
        else:
            msg = "Skipped VM idle checking"
            self.hutil.log_and_syslog(logging.INFO, msg)

        if self.exists_stop_flag():
            self.hutil.log_and_syslog(logging.INFO, "Installing patches is stopped/canceled")
            self.delete_stop_flag()
            return

        # Record the scheduled time
        waagent.AppendFileContents(self.history_scheduled, time.strftime("%Y-%m-%d %a", time.localtime()) + '\n' )
        # Record the open deleted files before patching
        self.open_deleted_files_before = self.check_open_deleted_files()

        retcode = self.stop_download()
        if retcode == 0:
            self.hutil.log_and_syslog(logging.WARNING, "Download time exceeded. The pending package will be \
                                downloaded in the next cycle")

        global start_patch_time
        start_patch_time = time.time()

        patchlist = self.get_pkg_to_patch(self.category_required)
        self._patch(self.category_required, patchlist)
        if not self.exists_stop_flag():
            self.hutil.log_and_syslog(logging.INFO, "Going to sleep for " + str(self.gap_between_stage) + "s")
            time.sleep(self.gap_between_stage)
            patchlist = self.get_pkg_to_patch(self.category_all)
            self._patch(self.category_all, patchlist)
        else:
            self.hutil.log_and_syslog(logging.INFO, "Installing patches (Category:" + self.category_all + ") is stopped/canceled")

        self.open_deleted_files_after = self.check_open_deleted_files()
        self.delete_stop_flag()
        #self.report()
        if self.check_healthy:
            self.hutil.log_and_syslog(logging.INFO, "Checking the VM is healthy after patching: " + str(VMStatusTest.is_vm_healthy()))
        if self.patched is not None and len(self.patched) > 0:
            self.reboot_if_required()

    def _patch(self, category, patchlist):
        if self.exists_stop_flag():
            self.hutil.log_and_syslog(logging.INFO, "Installing patches (Category:" + category + ") is stopped/canceled")
            return
        if not patchlist:
            self.hutil.log_and_syslog(logging.INFO, "No packages are available for update.")
            return
        self.hutil.log_and_syslog(logging.INFO, "Start to install " + str(len(patchlist)) +" patches (Category:" + category + ")")
        self.hutil.log_and_syslog(logging.INFO, "Patch list: " + ' '.join(patchlist))
        pkg_failed = []
        for pkg_name in patchlist:
            if pkg_name == 'walinuxagent':
                continue
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                self.hutil.log_and_syslog(logging.WARNING, "Patching time exceeded. The pending package will be \
                                patched in the next cycle")
                break
            retcode = self.patch_package(pkg_name)
            if retcode != 0:
                self.hutil.log_and_syslog(logging.ERROR, "Failed to patch the package:" + pkg_name)
                pkg_failed.append(' '.join([pkg_name, category]))
                continue
            self.patched.append(pkg_name)
            self.hutil.log_and_syslog(logging.INFO, "Package " + pkg_name + " is patched.")
            waagent.AppendFileContents(self.package_patched_path, pkg_name + ' ' + category + '\n')
        return pkg_failed

    def patch_one_off(self):
        """
        Called when startTime is empty string, which means a on-demand patch.
        """
        self.is_template()
        if self.check_idle:
            if VMStatusTest.is_vm_idle():
                msg = "Checking the VM is idle: True"
            else:
                msg = "Checking the VM is idle: False. Downloading is skipped."
            self.hutil.log_and_syslog(logging.INFO, msg)
            return
        else:
            msg = "Skipped VM idle checking"
            self.hutil.log_and_syslog(logging.INFO, msg)

        global start_patch_time
        start_patch_time = time.time()

        self.hutil.log_and_syslog(logging.INFO, "Going to patch one-off")
        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')

        # Record the open deleted files before patching
        self.open_deleted_files_before = self.check_open_deleted_files()

        pkg_failed = []
        retcode, patchlist_required = self.check(self.category_required)
        if retcode > 0:
            self.hutil.log_and_syslog(logging.ERROR, "Failed to check valid upgrades")
            sys.exit(1)
        if not patchlist_required:
            self.hutil.log_and_syslog(logging.INFO, "No packages are available for update. (Category:" + self.category_required + ")")
        else:
            pkg_required_failed = self._patch(self.category_required, patchlist_required)
            pkg_failed.extend(pkg_required_failed)
        if self.category == self.category_all:
            if not self.exists_stop_flag():
                self.hutil.log_and_syslog(logging.INFO, "Going to sleep for " + str(self.gap_between_stage) + "s")
                time.sleep(self.gap_between_stage)
                self.hutil.log_and_syslog(logging.INFO, "Going to patch one-off (Category:" + self.category_all + ")")
                retcode, patchlist_other = self.check(self.category_all)
                if retcode > 0:
                    self.hutil.log_and_syslog(logging.ERROR, "Failed to check valid upgrades")
                    sys.exit(1)
                patchlist_other = [pkg for pkg in patchlist_other if pkg not in patchlist_required]
                if not patchlist_other:
                    self.hutil.log_and_syslog(logging.INFO, "No packages are available for update. (Category:" + self.category_all + ")")
                else:
                    pkg_other_failed = self._patch(self.category_all, patchlist_other)
                    pkg_failed.extend(pkg_other_failed)
            else:
                self.hutil.log_and_syslog(logging.INFO, "Installing patches (Category:" + self.category_all + ") is stopped/canceled")
        shutil.copy2(self.package_patched_path, self.package_downloaded_path)
        for pkg in pkg_failed:
            waagent.AppendFileContents(self.package_downloaded_path, pkg + '\n')

        self.open_deleted_files_after = self.check_open_deleted_files()
        self.delete_stop_flag()
        #self.report()
        if self.check_healthy:
            self.hutil.log_and_syslog(logging.INFO, "Checking the VM is healthy after patching: " + str(VMStatusTest.is_vm_healthy()))
        if self.patched is not None and len(self.patched) > 0:
            self.reboot_if_required()

    def reboot_if_required(self):
        self.check_reboot()
        self.check_needs_restart()
        msg = ''
        if self.reboot_after_patch == 'NotRequired' and self.reboot_required:
            msg += 'Pending Reboot'
            if self.needs_restart:
                msg += ': ' + ' '.join(self.needs_restart)
            self.do_exit(0, 'Enable', 'success', '0', msg)
        if self.reboot_after_patch == 'Required':
            msg += "System going to reboot(Required)"
        elif self.reboot_after_patch == 'Auto' and self.reboot_required:
            msg += "System going to reboot(Auto)"
        elif self.reboot_after_patch == 'RebootIfNeed':
            if (self.reboot_required or self.needs_restart):
                msg += "System going to reboot(RebootIfNeed)"
        if msg:
            if self.needs_restart:
                msg += ': ' + ' '.join(self.needs_restart)
            self.hutil.log_and_syslog(logging.INFO, msg)
            retcode = waagent.Run('reboot')
            if retcode != 0:
                self.hutil.log_and_syslog(logging.ERROR, "Failed to reboot")

    def check_needs_restart(self):
        self.needs_restart.extend(self.get_pkg_needs_restart())
        patched_files = dict()
        for pkg in self.get_pkg_patched():
            cmd = ' '.join([self.pkg_query_cmd, pkg])
            try:
                retcode, output = waagent.RunGetOutput(cmd)
                patched_files[os.path.basename(pkg)] = [filename for filename in output.split("\n") if os.path.isfile(filename)]
            except Exception:
                self.hutil.log_and_syslog(logging.ERROR, "Failed to " + cmd)
        # for k,v in patched_files.items():
        #     self.hutil.log_and_syslog(logging.INFO, k + ": " + " ".join(v))
        open_deleted_files = list()
        for filename in self.open_deleted_files_after:
            if filename not in self.open_deleted_files_before:
                open_deleted_files.append(filename)
        # self.hutil.log_and_syslog(logging.INFO, "Open deleted files: " + " ".join(open_deleted_files))
        for pkg,files in patched_files.items():
            for filename in files:
                realpath = os.path.realpath(filename)
                if realpath in open_deleted_files and pkg not in self.needs_restart:
                     self.needs_restart.append(pkg)
        self.hutil.log_and_syslog(logging.INFO, "Packages needs to restart: " + " ".join(self.needs_restart))

    def get_pkg_needs_restart(self):
        return []

    def check_open_deleted_files(self):
        ret = list()
        retcode,output = waagent.RunGetOutput('lsof | grep "DEL"')
        if retcode == 0:
            for line in output.split('\n'):
                if line:
                    filename = line.split()[-1]
                    if filename not in ret:
                        ret.append(filename)
        return ret

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
        if not os.path.isfile(self.package_downloaded_path):
            return []
        pkg_to_patch = waagent.GetFileContents(self.package_downloaded_path)
        if not pkg_to_patch:
            return []
        patchlist = [line.split()[0] for line in pkg_to_patch.split('\n') if line.endswith(category)]
        return patchlist

    def get_pkg_patched(self):
        if not os.path.isfile(self.package_patched_path):
            return []
        pkg_patched = waagent.GetFileContents(self.package_patched_path)
        if not pkg_patched:
            return []
        patchedlist = [line.split()[0] for line in pkg_patched.split('\n') if line]
        return patchedlist

    def get_current_config(self):
        return 'Current Configuation: ' + ','.join(self.current_config_list)
        
    def is_template(self):
        if not VMStatusTestTemplate:
            msg = "User does not provide VM status test scripts."
            msg += " The default template is used."
            self.hutil.log_and_syslog(logging.WARNING, msg)
