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

import os
import sys
import re
import json
import random
import shutil
import time
import datetime
import logging
import logging.handlers

from Utils.WAAgentUtil import waagent
from ConfigOptions import ConfigOptions

mfile = os.path.join(os.getcwd(), 'HandlerManifest.json')
with open(mfile,'r') as f:
    manifest = json.loads(f.read())[0]
    Version = manifest['version']

StatusTest = {
    "Scheduled" : {
        "Idle" : None,
        "Healthy" : None
    },
    "Oneoff" : {
        "Idle" : None,
        "Healthy" : None
    }
}

try:
    from scheduled.idleTest import is_vm_idle
    StatusTest["Scheduled"]["Idle"] = is_vm_idle
except:
    pass

try:
    from oneoff.idleTest import is_vm_idle
    StatusTest["Oneoff"]["Idle"] = is_vm_idle
except:
    pass

try:
    from scheduled.healthyTest import is_vm_healthy
    StatusTest["Scheduled"]["Healthy"] = is_vm_healthy
except:
    pass

try:
    from oneoff.healthyTest import is_vm_healthy
    StatusTest["Oneoff"]["Healthy"] = is_vm_healthy
except:
    pass


class AbstractPatching(object):
    """
    AbstractPatching defines a skeleton neccesary for a concrete Patching class.
    """
    def __init__(self, hutil):
        self.hutil = hutil
        self.syslogger = None

        self.patched = []
        self.to_patch = []
        self.downloaded = []
        self.download_retry_queue = []

        # Patching Configuration
        self.disabled = None
        self.stop = None
        self.reboot_after_patch = None
        self.category = None
        self.install_duration = None
        self.oneoff = None
        self.interval_of_weeks = None
        self.day_of_week = None
        self.start_time = None
        self.download_time = None
        self.download_duration = 3600
        self.gap_between_stage = 60
        self.current_configs = dict()

        self.category_required = ConfigOptions.category["required"]
        self.category_all = ConfigOptions.category["all"]

        # Crontab Variables
        self.crontab = '/etc/crontab'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'

        # Path Variables
        self.cwd = os.getcwd()
        self.package_downloaded_path = os.path.join(self.cwd, 'package.downloaded')
        self.package_patched_path = os.path.join(self.cwd, 'package.patched')
        self.stop_flag_path = os.path.join(self.cwd, 'StopOSPatching')
        self.history_scheduled = os.path.join(self.cwd, 'scheduled/history')
        self.scheduled_configs_file = os.path.join(self.cwd, 'scheduled/configs')
        self.dist_upgrade_list = None
        self.dist_upgrade_list_key = 'distUpgradeList'
        self.dist_upgrade_all = False
        self.dist_upgrade_all_key = 'distUpgradeAll'

        # Reboot Requirements
        self.reboot_required = False
        self.open_deleted_files_before = list()
        self.open_deleted_files_after = list()
        self.needs_restart = list()

    def is_string_none_or_empty(self, str):
        if str is None or len(str) < 1:
            return True
        return False
    
    def parse_settings(self, settings):
        disabled = settings.get("disabled")
        if disabled is None or str(disabled).lower() not in ConfigOptions.disabled:
            msg = "The value of parameter \"disabled\" is empty or invalid. Set it False by default."
            self.log_and_syslog(logging.WARNING, msg)
            self.disabled = False
        else:
            if str(disabled).lower() == "true":
                self.disabled = True
            else:
                self.disabled = False
        self.current_configs["disabled"] = str(self.disabled)
        if self.disabled:
            msg = "The extension is disabled."
            self.log_and_syslog(logging.WARNING, msg)
            return

        stop = settings.get("stop")
        if stop is None or str(stop).lower() not in ConfigOptions.stop:
            msg = "The value of parameter \"stop\" is empty or invalid. Set it False by default."
            self.log_and_syslog(logging.WARNING, msg)
            self.stop = False
        else:
            if str(stop).lower() == 'true':
                self.stop = True
            else:
                self.stop = False
        self.current_configs["stop"] = str(self.stop)

        reboot_after_patch = settings.get("rebootAfterPatch")
        if reboot_after_patch is None or reboot_after_patch.lower() not in ConfigOptions.reboot_after_patch:
            msg = "The value of parameter \"rebootAfterPatch\" is empty or invalid. Set it \"rebootifneed\" by default."
            self.log_and_syslog(logging.WARNING, msg)
            self.reboot_after_patch = ConfigOptions.reboot_after_patch[0]
        else:
            self.reboot_after_patch = reboot_after_patch.lower()
        waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                  op=waagent.WALAEventOperation.Enable,
                                  isSuccess=True,
                                  version=Version,
                                  message="rebootAfterPatch="+self.reboot_after_patch)
        self.current_configs["rebootAfterPatch"] = self.reboot_after_patch

        category = settings.get('category')
        if category is None or category.lower() not in ConfigOptions.category.values():
            msg = "The value of parameter \"category\" is empty or invalid. Set it " + self.category_required + " by default."
            self.log_and_syslog(logging.WARNING, msg)
            self.category = self.category_required
        else:
            self.category = category.lower()
        waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                  op=waagent.WALAEventOperation.Enable,
                                  isSuccess=True,
                                  version=Version,
                                  message="category="+self.category)
        self.current_configs["category"] =  self.category
        
        self.dist_upgrade_list = settings.get(self.dist_upgrade_list_key)
        if not self.is_string_none_or_empty(self.dist_upgrade_list):
            self.current_configs[self.dist_upgrade_list_key] = self.dist_upgrade_list

        dist_upgrade_all = settings.get(self.dist_upgrade_all_key)
        if dist_upgrade_all is None:
            msg = "The value of parameter \"{0}\" is empty or invalid. Set it false by default.".format(self.dist_upgrade_all_key)
            self.log_and_syslog(logging.INFO, msg)
            self.dist_upgrade_all = False
        elif str(dist_upgrade_all).lower() == 'true':
            self.dist_upgrade_all = True
        else:
            self.dist_upgrade_all = False
        self.current_configs[self.dist_upgrade_all_key] = str(self.dist_upgrade_all)
        
        check_hrmin = re.compile(r'^[0-9]{1,2}:[0-9]{1,2}$')
        install_duration = settings.get('installDuration')
        if install_duration is None or not re.match(check_hrmin, install_duration):
            msg = "The value of parameter \"installDuration\" is empty or invalid. Set it 1 hour by default."
            self.log_and_syslog(logging.WARNING, msg)
            self.install_duration = 3600
            self.current_configs["installDuration"] = "01:00"
        else:
            hr_min = install_duration.split(':')
            self.install_duration = int(hr_min[0]) * 3600 + int(hr_min[1]) * 60
            self.current_configs["installDuration"] = install_duration
        if self.install_duration <= 300:
            msg = "The value of parameter \"installDuration\" is smaller than 5 minutes. The extension will not reserve 5 minutes for reboot. It is recommended to set \"installDuration\" more than 30 minutes."
            self.log_and_syslog(logging.WARNING, msg)
        else:
            msg = "The extension will reserve 5 minutes for reboot."
            # 5 min for reboot
            self.install_duration -= 300
            self.log_and_syslog(logging.INFO, msg)

        # The parameter "downloadDuration" is not exposed to users. So there's no log.
        download_duration = settings.get('downloadDuration')
        if download_duration is not None and re.match(check_hrmin, download_duration):
            hr_min = download_duration.split(':')
            self.download_duration = int(hr_min[0]) * 3600 + int(hr_min[1]) * 60

        oneoff = settings.get('oneoff')
        if oneoff is None or str(oneoff).lower() not in ConfigOptions.oneoff:
            msg = "The value of parameter \"oneoff\" is empty or invalid. Set it False by default."
            self.log_and_syslog(logging.WARNING, msg)
            self.oneoff = False
        else:
            if str(oneoff).lower() == "true":
                self.oneoff = True
                msg = "The extension will run in one-off mode."
            else:
                self.oneoff = False
                msg = "The extension will run in scheduled task mode."
            self.log_and_syslog(logging.INFO, msg)
        self.current_configs["oneoff"] = str(self.oneoff)

        if not self.oneoff:
            start_time = settings.get('startTime')
            if start_time is None or not re.match(check_hrmin, start_time):
                msg = "The parameter \"startTime\" is empty or invalid. It defaults to 03:00."
                self.log_and_syslog(logging.WARNING, msg)
                start_time = "03:00"
            self.start_time = datetime.datetime.strptime(start_time, '%H:%M')
            self.download_time = self.start_time - datetime.timedelta(seconds=self.download_duration)
            self.current_configs["startTime"] = start_time
 
            day_of_week = settings.get("dayOfWeek")
            if day_of_week is None or day_of_week == "":
                msg = "The parameter \"dayOfWeek\" is empty. dayOfWeek defaults to Everyday."
                self.log_and_syslog(logging.WARNING, msg)
                day_of_week = "everyday"
                self.day_of_week = ConfigOptions.day_of_week["everyday"]
            else:
                for day in day_of_week.split('|'):
                    day = day.strip().lower()
                    if day not in ConfigOptions.day_of_week:
                        msg = "The parameter \"dayOfWeek\" is invalid. dayOfWeek defaults to Everyday."
                        self.log_and_syslog(logging.WARNING, msg)
                        day_of_week = "everyday"
                        break
                if "everyday" in day_of_week:
                    self.day_of_week = ConfigOptions.day_of_week["everyday"]
                else:
                    self.day_of_week = [ConfigOptions.day_of_week[day.strip().lower()] for day in day_of_week.split('|')]
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op=waagent.WALAEventOperation.Enable,
                                      isSuccess=True,
                                      version=Version,
                                      message="dayOfWeek=" + day_of_week)
            self.current_configs["dayOfWeek"] = day_of_week

            interval_of_weeks = settings.get('intervalOfWeeks')
            if interval_of_weeks is None or interval_of_weeks not in ConfigOptions.interval_of_weeks:
                msg = "The parameter \"intervalOfWeeks\" is empty or invalid. intervalOfWeeks defaults to 1."
                self.log_and_syslog(logging.WARNING, msg)
                self.interval_of_weeks = '1'
            else:
                self.interval_of_weeks = interval_of_weeks
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op=waagent.WALAEventOperation.Enable,
                                      isSuccess=True,
                                      version=Version,
                                      message="intervalOfWeeks="+self.interval_of_weeks)
            self.current_configs["intervalOfWeeks"] = self.interval_of_weeks

            # Save the latest configuration for scheduled task to avoid one-off mode's affection
            waagent.SetFileContents(self.scheduled_configs_file, json.dumps(self.current_configs))

        msg = "Current Configuration: " + self.get_current_config()
        self.log_and_syslog(logging.INFO, msg)

    def install(self):
        pass

    def enable(self):
        if self.stop:
            self.stop_download()
            self.create_stop_flag()
            return
        self.delete_stop_flag()
        if not self.disabled and self.oneoff:
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
            self.log_and_syslog(logging.ERROR, output)
        if output != '':
            retcode, output2 = waagent.RunGetOutput("ps -ef | awk '{if($3==" + output.strip() + ") {print $2}}'")
            if retcode > 0:
                self.log_and_syslog(logging.ERROR, output2)
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
            self.log_and_syslog(logging.ERROR, output)

    def download(self):
        # Read the latest configuration for scheduled task
        settings = json.loads(waagent.GetFileContents(self.scheduled_configs_file))
        self.parse_settings(settings)

        self.provide_vm_status_test(StatusTest["Scheduled"])
        if not self.check_vm_idle(StatusTest["Scheduled"]):
            return

        if self.exists_stop_flag():
            self.log_and_syslog(logging.INFO, "Downloading patches is stopped/canceled")
            return

        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')

        start_download_time = time.time()
        # Installing security patches is mandatory
        self._download(self.category_required)
        if self.category == self.category_all:
            self._download(self.category_all)
        self.retry_download()
        end_download_time = time.time()
        waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                  op=waagent.WALAEventOperation.Download,
                                  isSuccess=True,
                                  version=Version,
                                  message=" ".join(["Real downloading time is", str(round(end_download_time-start_download_time,3)), "s"]))

    def _download(self, category):
        self.log_and_syslog(logging.INFO, "Start to check&download patches (Category:" + category + ")")
        retcode, downloadlist = self.check(category)
        if retcode > 0:
            msg = "Failed to check valid upgrades"
            self.log_and_syslog(logging.ERROR, msg)
            self.hutil.do_exit(1, 'Enable', 'error', '0', msg)
        if 'walinuxagent' in downloadlist:
            downloadlist.remove('walinuxagent')
        if not downloadlist:
            self.log_and_syslog(logging.INFO, "No packages are available for update.")
            return
        self.log_and_syslog(logging.INFO, "There are " + str(len(downloadlist)) + " packages to upgrade.")
        self.log_and_syslog(logging.INFO, "Download list: " + ' '.join(downloadlist))
        for pkg_name in downloadlist:
            if pkg_name in self.downloaded:
                continue
            retcode = self.download_package(pkg_name)
            if retcode != 0:
                self.log_and_syslog(logging.ERROR, "Failed to download the package: " + pkg_name)
                self.log_and_syslog(logging.INFO, "Put {0} into a retry queue".format(pkg_name))
                self.download_retry_queue.append((pkg_name, category))
                continue
            self.downloaded.append(pkg_name)
            self.log_and_syslog(logging.INFO, "Package " + pkg_name + " is downloaded.")
            waagent.AppendFileContents(self.package_downloaded_path, pkg_name + ' ' + category + '\n')

    def retry_download(self):
        retry_count = 0
        max_retry_count = 12
        self.log_and_syslog(logging.INFO, "Retry queue: {0}".format(
            " ".join([pkg_name for pkg_name,category in self.download_retry_queue])))
        while self.download_retry_queue:
            pkg_name, category = self.download_retry_queue[0]
            self.download_retry_queue = self.download_retry_queue[1:]
            retcode = self.download_package(pkg_name)
            if retcode == 0:
                self.downloaded.append(pkg_name)
                self.log_and_syslog(logging.INFO, "Package " + pkg_name + " is downloaded.")
                waagent.AppendFileContents(self.package_downloaded_path, pkg_name + ' ' + category + '\n')
            else:
                self.log_and_syslog(logging.ERROR, "Failed to download the package: " + pkg_name)
                self.log_and_syslog(logging.INFO, "Put {0} back into a retry queue".format(pkg_name))
                self.download_retry_queue.append((pkg_name,category))
                retry_count = retry_count + 1
                if retry_count > max_retry_count:
                    err_msg = ("Failed to download after {0} retries, "
                        "retry queue: {1}").format(max_retry_count,
                        " ".join([pkg_name for pkg_name,category in self.download_retry_queue]))
                    self.log_and_syslog(logging.ERROR, err_msg)
                    waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                              op=waagent.WALAEventOperation.Download,
                                              isSuccess=False,
                                              version=Version,
                                              message=err_msg)
                    break
                k = retry_count if (retry_count < 10) else 10
                interval = int(random.uniform(0, 2 ** k))
                self.log_and_syslog(logging.INFO, ("Sleep {0}s before "
                    "the next retry, current retry_count = {1}").format(interval, retry_count))
                time.sleep(interval)

    def patch(self):
        # Read the latest configuration for scheduled task
        settings = json.loads(waagent.GetFileContents(self.scheduled_configs_file))
        self.parse_settings(settings)

        if not self.check_vm_idle(StatusTest["Scheduled"]):
            return

        if self.exists_stop_flag():
            self.log_and_syslog(logging.INFO, "Installing patches is stopped/canceled")
            self.delete_stop_flag()
            return

        # Record the scheduled time
        waagent.AppendFileContents(self.history_scheduled, time.strftime("%Y-%m-%d %a", time.localtime()) + '\n' )
        # Record the open deleted files before patching
        self.open_deleted_files_before = self.check_open_deleted_files()

        retcode = self.stop_download()
        if retcode == 0:
            self.log_and_syslog(logging.WARNING, "Download time exceeded. The pending package will be downloaded in the next cycle")
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op=waagent.WALAEventOperation.Download,
                                      isSuccess=False,
                                      version=Version,
                                      message="Downloading time out")

        global start_patch_time
        start_patch_time = time.time()

        pkg_failed = []
        is_time_out = [False, False]
        patchlist = self.get_pkg_to_patch(self.category_required)
        is_time_out[0],failed = self._patch(self.category_required, patchlist)
        pkg_failed.extend(failed)
        if not self.exists_stop_flag():
            if not is_time_out[0]:
                patchlist = self.get_pkg_to_patch(self.category_all)
                if len(patchlist) == 0:
                    self.log_and_syslog(logging.INFO, "No packages are available for update. (Category:" + self.category_all + ")")
                else:
                    self.log_and_syslog(logging.INFO, "Going to sleep for " + str(self.gap_between_stage) + "s")
                    time.sleep(self.gap_between_stage)
                    is_time_out[1],failed = self._patch(self.category_all, patchlist)
                    pkg_failed.extend(failed)
        else:
            msg = "Installing patches (Category:" + self.category_all + ") is stopped/canceled"
            self.log_and_syslog(logging.INFO, msg)
        if is_time_out[0] or is_time_out[1]:
            msg = "Patching time out"
            self.log_and_syslog(logging.WARNING, msg)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Patch",
                                      isSuccess=False,
                                      version=Version,
                                      message=msg)

        self.open_deleted_files_after = self.check_open_deleted_files()
        self.delete_stop_flag()
        #self.report()
        if StatusTest["Scheduled"]["Healthy"]:
            is_healthy = StatusTest["Scheduled"]["Healthy"]()
            msg = "Checking the VM is healthy after patching: " + str(is_healthy)
            self.log_and_syslog(logging.INFO, msg)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Check healthy",
                                      isSuccess=is_healthy,
                                      version=Version,
                                      message=msg)
        if self.patched is not None and len(self.patched) > 0:
            self.reboot_if_required()

    def _patch(self, category, patchlist):
        if self.exists_stop_flag():
            self.log_and_syslog(logging.INFO, "Installing patches (Category:" + category + ") is stopped/canceled")
            return False,list()
        if not patchlist:
            self.log_and_syslog(logging.INFO, "No packages are available for update.")
            return False,list()
        self.log_and_syslog(logging.INFO, "Start to install " + str(len(patchlist)) +" patches (Category:" + category + ")")
        self.log_and_syslog(logging.INFO, "Patch list: " + ' '.join(patchlist))
        pkg_failed = []
        for pkg_name in patchlist:
            if pkg_name == 'walinuxagent':
                continue
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                msg = "Patching time exceeded. The pending package will be patched in the next cycle"
                self.log_and_syslog(logging.WARNING, msg)
                return True,pkg_failed
            retcode = self.patch_package(pkg_name)
            if retcode != 0:
                self.log_and_syslog(logging.ERROR, "Failed to patch the package:" + pkg_name)
                pkg_failed.append(' '.join([pkg_name, category]))
                continue
            self.patched.append(pkg_name)
            self.log_and_syslog(logging.INFO, "Package " + pkg_name + " is patched.")
            waagent.AppendFileContents(self.package_patched_path, pkg_name + ' ' + category + '\n')
        return False,pkg_failed

    def patch_one_off(self):
        """
        Called when startTime is empty string, which means a on-demand patch.
        """
        self.provide_vm_status_test(StatusTest["Oneoff"])
        if not self.check_vm_idle(StatusTest["Oneoff"]):
            return

        global start_patch_time
        start_patch_time = time.time()

        self.log_and_syslog(logging.INFO, "Going to patch one-off")
        waagent.SetFileContents(self.package_downloaded_path, '')
        waagent.SetFileContents(self.package_patched_path, '')

        # Record the open deleted files before patching
        self.open_deleted_files_before = self.check_open_deleted_files()

        pkg_failed = []
        is_time_out = [False, False]
        retcode, patchlist_required = self.check(self.category_required)
        if retcode > 0:
            msg = "Failed to check valid upgrades"
            self.log_and_syslog(logging.ERROR, msg)
            self.hutil.do_exit(1, 'Enable', 'error', '0', msg)
        if not patchlist_required:
            self.log_and_syslog(logging.INFO, "No packages are available for update. (Category:" + self.category_required + ")")
        else:
            is_time_out[0],failed = self._patch(self.category_required, patchlist_required)
            pkg_failed.extend(failed)
        if self.category == self.category_all:
            if not self.exists_stop_flag():
                if not is_time_out[0]:
                    retcode, patchlist_other = self.check(self.category_all)
                    if retcode > 0:
                        msg = "Failed to check valid upgrades"
                        self.log_and_syslog(logging.ERROR, msg)
                        self.hutil.do_exit(1, 'Enable', 'error', '0', msg)
                    patchlist_other = [pkg for pkg in patchlist_other if pkg not in patchlist_required]
                    if len(patchlist_other) == 0:
                        self.log_and_syslog(logging.INFO, "No packages are available for update. (Category:" + self.category_all + ")")
                    else:
                        self.log_and_syslog(logging.INFO, "Going to sleep for " + str(self.gap_between_stage) + "s")
                        time.sleep(self.gap_between_stage)
                        self.log_and_syslog(logging.INFO, "Going to patch one-off (Category:" + self.category_all + ")")
                        is_time_out[1],failed = self._patch(self.category_all, patchlist_other)
                        pkg_failed.extend(failed)
            else:
                self.log_and_syslog(logging.INFO, "Installing patches (Category:" + self.category_all + ") is stopped/canceled")

        if is_time_out[0] or is_time_out[1]:
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Oneoff Patch",
                                      isSuccess=False,
                                      version=Version,
                                      message="Patching time out")

        shutil.copy2(self.package_patched_path, self.package_downloaded_path)
        for pkg in pkg_failed:
            waagent.AppendFileContents(self.package_downloaded_path, pkg + '\n')

        self.open_deleted_files_after = self.check_open_deleted_files()
        self.delete_stop_flag()
        #self.report()
        if StatusTest["Oneoff"]["Healthy"]:
            is_healthy = StatusTest["Oneoff"]["Healthy"]()
            msg = "Checking the VM is healthy after patching: " + str(is_healthy)
            self.log_and_syslog(logging.INFO, msg)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Check healthy",
                                      isSuccess=is_healthy,
                                      version=Version,
                                      message=msg)
        if self.patched is not None and len(self.patched) > 0:
            self.reboot_if_required()

    def reboot_if_required(self):
        self.check_reboot()
        self.check_needs_restart()
        msg = ''
        if self.reboot_after_patch == 'notrequired' and self.reboot_required:
            msg += 'Pending Reboot'
            if self.needs_restart:
                msg += ': ' + ' '.join(self.needs_restart)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Reboot",
                                      isSuccess=False,
                                      version=Version,
                                      message=" ".join([self.reboot_after_patch, msg,
                                                       str(len(self.needs_restart)),
                                                       "packages need to restart"]))
            self.hutil.do_exit(0, 'Enable', 'success', '0', msg)
        if self.reboot_after_patch == 'required':
            msg += "System going to reboot(Required)"
        elif self.reboot_after_patch == 'auto' and self.reboot_required:
            msg += "System going to reboot(Auto)"
        elif self.reboot_after_patch == 'rebootifneed':
            if (self.reboot_required or self.needs_restart):
                msg += "System going to reboot(RebootIfNeed)"
        if msg:
            if self.needs_restart:
                msg += ': ' + ' '.join(self.needs_restart)
            self.log_and_syslog(logging.INFO, msg)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Reboot",
                                      isSuccess=True,
                                      version=Version,
                                      message="Reboot")
            retcode = waagent.Run('reboot')
            if retcode != 0:
                self.log_and_syslog(logging.ERROR, "Failed to reboot")
                waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                          op="Reboot",
                                          isSuccess=False,
                                          version=Version,
                                          message="Failed to reboot")
        else:
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Reboot",
                                      isSuccess=False,
                                      version=Version,
                                      message="Not reboot")

    def check_needs_restart(self):
        self.needs_restart.extend(self.get_pkg_needs_restart())
        patched_files = dict()
        for pkg in self.get_pkg_patched():
            cmd = ' '.join([self.pkg_query_cmd, pkg])
            try:
                retcode, output = waagent.RunGetOutput(cmd)
                patched_files[os.path.basename(pkg)] = [filename for filename in output.split("\n") if os.path.isfile(filename)]
            except Exception:
                self.log_and_syslog(logging.ERROR, "Failed to " + cmd)
        # for k,v in patched_files.items():
        #     self.log_and_syslog(logging.INFO, k + ": " + " ".join(v))
        open_deleted_files = list()
        for filename in self.open_deleted_files_after:
            if filename not in self.open_deleted_files_before:
                open_deleted_files.append(filename)
        # self.log_and_syslog(logging.INFO, "Open deleted files: " + " ".join(open_deleted_files))
        for pkg,files in patched_files.items():
            for filename in files:
                realpath = os.path.realpath(filename)
                if realpath in open_deleted_files and pkg not in self.needs_restart:
                     self.needs_restart.append(pkg)
        msg = "Packages needs to restart: "
        pkgs = " ".join(self.needs_restart)
        if pkgs:
            msg += pkgs
        else:
            msg = "There is no package which needs to restart"
        self.log_and_syslog(logging.INFO, msg)

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
        if patchlist is None:
            return []
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
        current_configs = []
        for k,v in self.current_configs.items():
            current_configs.append(k + "=" + v)
        return ",".join(current_configs)

    def provide_vm_status_test(self, status_test):
        for status,provided in status_test.items():
            if provided is None:
                provided = "False"
                level = logging.WARNING
            else:
                provided = "True"
                level = logging.INFO
            msg = "The VM %s test script is provided: %s" % (status, provided)
            self.log_and_syslog(level, msg)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="provides %s test script" % (status,),
                                      isSuccess=provided,
                                      version=Version,
                                      message=msg)

    def check_vm_idle(self, status_test):
        is_idle = True
        if status_test["Idle"]:
            is_idle = status_test["Idle"]()
            msg = "Checking the VM is idle: " + str(is_idle)
            self.log_and_syslog(logging.INFO, msg)
            waagent.AddExtensionEvent(name=self.hutil.get_name(),
                                      op="Check idle",
                                      isSuccess=is_idle,
                                      version=Version,
                                      message=msg)
            if not is_idle:
                self.log_and_syslog(logging.WARNING, "Current Operation is skipped.")
        return is_idle

    def log_and_syslog(self, level, message):
        if level == logging.INFO:
            self.hutil.log(message)
        elif level == logging.WARNING:
            self.hutil.log(" ".join(["Warning:", message]))
        elif level == logging.ERROR:
            self.hutil.error(message)
        if self.syslogger is None:
            self.init_syslog()
        self.syslog(level, message)

    def init_syslog(self):
        self.syslogger = logging.getLogger(self.hutil.get_name())
        self.syslogger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(name)s: %(levelname)s %(message)s')
        try:
            handler = logging.handlers.SysLogHandler(address='/dev/log')
            handler.setFormatter(formatter)
            self.syslogger.addHandler(handler)
        except:
            self.syslogger = None
            self.hutil.error("Syslog is not ready.")

    def syslog(self, level, message):
        if self.syslogger is None:
            return
        if level == logging.INFO:
            self.syslogger.info(message)
        elif level == logging.WARNING:
            self.syslogger.warning(message)
        elif level == logging.ERROR:
            self.syslogger.error(message)

