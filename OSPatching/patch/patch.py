#!/usr/bin/python
#
# OSPatching extension
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

            self.hutil.log("Configurations:\ndisabled: %s\ndayOfWeek: %s\nstartTime: %s\ndownloadTime: %s\ninstallDuration: %s\ncategory: %s\n" % (self.disabled, ','.join([str(dow) for dow in self.day_of_week]), str(self.start_time.strftime('%H:%M')), str(self.download_time.hour), str(self.install_duration), self.category))

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


class UbuntuPatching(AbstractPatching):
    def __init__(self, hutil):
        super(UbuntuPatching,self).__init__(hutil)
        self.clean_cmd = 'apt-get clean'
        self.check_cmd = 'apt-get -s upgrade'
        self.download_cmd = 'apt-get -d -y install'
        self.patch_cmd = 'apt-get -y install'
        self.status_cmd = 'apt-cache show'

    def parse_settings(self, settings):
        super(UbuntuPatching,self).parse_settings(settings)
        if self.category == 'Important':
            waagent.Run('grep "-security" /etc/apt/sources.list | sudo grep -v "#" > /etc/apt/security.sources.list')
            self.download_cmd = self.download_cmd + ' -o Dir::Etc::SourceList=/etc/apt/security.sources.list'

    def check(self):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        retcode,output = waagent.RunGetOutput(self.check_cmd)
        if retcode > 0:
            self.hutil.error("Failed to check valid upgrades")
        start = output.find('The following packages will be upgraded')
        if start == -1:
            self.hutil.log("No package to upgrade")
            sys.exit(0)
        start = output.find('\n', start)
        end = output.find('upgraded', start)
        output = re.split(r'\s+', output[start:end].strip())
        output.pop()
        self.to_download = output

    def clean(self):
        retcode,output = waagent.RunGetOutput(self.clean_cmd)
        if retcode > 0:
            self.hutil.error("Failed to erase downloaded archive files")

    def download(self):
        start_download_time = time.time()
        self.check()
        self.clean()
        for package_to_download in self.to_download:
            retcode = waagent.Run(self.download_cmd + ' ' + package_to_download)
            if retcode > 0:
                self.hutil.error("Failed to download the package: " + package_to_download)
                continue
            self.downloaded.append(package_to_download)
            current_download_time = time.time()
            if current_download_time - start_download_time > self.download_duration:
                break
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
            for package_downloaded in self.downloaded:
                self.to_download.remove(package_downloaded)
                f.write(package_downloaded + '\n')

    def reboot_if_required(self):
        reboot_required = '/var/run/reboot-required'
        if os.path.isfile(reboot_required):
            retcode = waagent.Run('reboot')
            if retcode > 0:
                self.hutil.error("Failed to reboot")

    def patch(self):
        start_patch_tim = time.time()
        try:
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'r') as f:
                self.to_patch = [package_downloaded.strip() for package_downloaded in f.readlines()]
        except IOError, e:
            self.hutil.error(str(e))
            self.to_patch = []
        for package_to_patch in self.to_patch:
            retcode = waagent.Run(self.patch_cmd + ' ' + package_to_patch)
            if retcode > 0:
                self.hutil.error("Failed to patch the package:" + package_to_patch)
                continue
            self.patched.append(package_to_patch)
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                break
        with open(os.path.join(waagent.LibDir, 'package.patched'), 'w') as f:
            for package_patched in self.patched:
                self.to_patch.remove(package_patched)
                f.write(package_patched + '\n')
        self.report()
        self.reboot_if_required()

    def report(self):
        status = {}
        package_patched = 'update-manager-core'
        status[package_patched] = {}
        retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + package_patched)
        output = output.split('\n\n')[0]
        self.hutil.log(output)

    def install(self):
        """
        Install for dependencies.
        """
        # /var/run/reboot-required is not created unless the update-notifier-common package is installed
        retcode = waagent.Run('apt-get -y install update-notifier-common')
        if retcode > 0:
            self.hutil.error("Failed to install update-notifier-common")


class redhatPatching(AbstractPatching):
    def __init__(self):
        super(redhatPatching,self).__init__()
        self.cron_restart_cmd = 'service crond restart'
        self.check_cmd = 'yum -q check-update'
        self.clean_cmd = 'yum clean packages'
        self.download_cmd = 'yum -q -y --downloadonly update'
        self.patch_cmd = 'yum -y update'
        self.status_cmd = 'yum -q info'
        # self.cache_dir = '/var/cache/yum/'
        # retcode,output = waagent.RunGetOutput('cd '+self.cache_dir+';find . -name "updates"')
        # self.download_dir = os.path.join(self.cache_dir, output.strip('.\n/') + '/packages')

    def parse_settings(self, settings):
        super(redhatPatching,self).parse_settings(settings)
        if self.category == 'Important':
            self.download_cmd = 'yum -q -y --downloadonly --security update'

    def check(self):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        retcode,output = waagent.RunGetOutput(self.check_cmd, chk_err=False)
        output = re.split(r'\s+', output.strip())
        self.to_download = output[0::3]

    def clean(self):
        """
        Remove downloaded package.
        Option "keepcache" in /etc/yum.conf is set to 0 by default,
        which deletes the downloaded package after installed.
        This function cleans the cache just in case.
        """
        retcode,output = waagent.RunGetOutput(self.clean_cmd)
        if retcode > 0:
            print "Failed to erase downloaded archive files"

    def download(self):
        start_download_time = time.time()
        self.check()
        self.clean()
        count = 0
        for package_to_download in self.to_download:
            count += 1
            retcode = waagent.Run(self.download_cmd + ' ' + package_to_download, chk_err=False)
            self.downloaded.append(package_to_download)
            current_download_time = time.time()
            if count > 2:
                break
            if current_download_time - start_download_time > self.download_duration:
                break
        with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'w') as f:
            for package_downloaded in self.downloaded:
                self.to_download.remove(package_downloaded)
                f.write(package_downloaded + '\n')

    def install(self):
        """
        Install for dependencies.
        """
        # For yum --downloadonly option
        retcode = waagent.Run('yum -y install yum-downloadonly')
        if retcode > 0:
            print "Failed to install yum-downloadonly"

        # For yum --security option
        retcode = waagent.Run('yum -y install yum-plugin-security')
        if retcode > 0:
            print "Failed to install yum-plugin-security"

    def patch(self):
        start_patch_time = time.time()
        try:
            with open(os.path.join(waagent.LibDir, 'package.downloaded'), 'r') as f:
                self.to_patch = [package_downloaded.strip() for package_downloaded in f.readlines()]
        except IOError, e:
            print str(e)
            self.to_patch = []
        for package_to_patch in self.to_patch:
            retcode = waagent.Run(self.patch_cmd + ' ' + package_to_patch)
            if retcode > 0:
                print "Failed to patch the package:" + package_to_patch
                continue
            self.patched.append(package_to_patch)
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                break
        with open(os.path.join(waagent.LibDir, 'package.patched'), 'w') as f:
            for package_patched in self.patched:
                self.to_patch.remove(package_patched)
                f.write(package_patched + '\n')
        self.report()
        self.reboot_if_required()

    def reboot_if_required(self):
        """
        A reboot should be only necessary when kernel has been upgraded.
        """
        retcode,last_kernel = waagent.RunGetOutput('rpm -q --last kernel | perl -pe \'s/^kernel-(\S+).*/$1/\' | head -1')
        retcode,current_kernel = waagent.RunGetOutput('uname -r')
        if last_kernel == current_kernel:
            retcode = waagent.Run('reboot')
            if retcode > 0:
                print "Failed to reboot"

    def report(self):
        status = {}
        for package_patched in self.patched:
            status[package_patched] = {}
            retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + package_patched)
            print output


class centosPatching(redhatPatching):
    def __init__(self):
        super(centosPatching,self).__init__()


class SuSEPatching(AbstractPatching):
    def __init__(self):
        super(SuSEPatching,self).__init__()
        self.patch_cmd = 'zypper --non-interactive patch --auto-agree-with-licenses --with-interactive'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'
        self.crontab = '/etc/crontab'
        self.patching_cron = '/tmp/patching_cron'
