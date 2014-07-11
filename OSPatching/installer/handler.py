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

#####################################################################################
# Will be deleted after release
#
# Template for configuring Patching
# protect_settings = {
#     "disabled" : "true|false",
#     "dayOfWeek" : "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Everyday",
#     "startTime" : "hr:min",                                                            # UTC time
#     "category" : "Important | ImportantAndRecommended",
#     "installDuration" : "hr:min"                                                       # in 30 minute increments
# }

protect_settings_disabled = {
    "disabled":"true",
}

protect_settings = {
    "disabled" : "false",
    "dayOfWeek" : "Sunday|Monday|Wednesday|Thursday|Friday|Saturday",
    "startTime" : "05:00",                                                            # UTC time
    "category" : "Important",
    "installDuration" : "00:30"                                                       # in 30 minute increments
}
#####################################################################################

# Global variables definition
# waagent has no '.py' therefore create waagent module import manually.
waagent=imp.load_source('waagent','/usr/sbin/waagent')
Util=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')
from waagent import LoggerInit

LoggerInit('/var/log/waagent.log','/dev/stdout')
ExtensionShortName = 'OSPatching'
waagent.Log("%s started to handle." %(ExtensionShortName)) 
logfile=waagent.Log
BeginCertificateTag = '-----BEGIN CERTIFICATE-----'
EndCertificateTag = '-----END CERTIFICATE-----'
OutputSplitter = ';'


###########################################################
# BEGIN PATCHING CLASS DEFS
###########################################################
###########################################################
#       AbstractPatching
###########################################################
class AbstractPatching(object):
    """
    AbstractPatching defines a skeleton neccesary for a concrete Patching class.
    """
    def __init__(self, settings):
        self.patched = []
        self.to_patch = []
        self.downloaded = []
        self.to_download = []

        self.download_duration = 3600

        self.crontab = '/etc/crontab'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'

        self.disabled = settings.get('disabled')
        if self.disabled is None:
            print "WARNING: the value of option \"disabled\" not specified in configuration\n Set it False by default"
            self.disabled = 'false'
        self.disabled = self.disabled.lower()
        if self.disabled == 'false':
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
            self.start_time = time.strptime(start_time, '%H:%M')

            self.download_time = self.start_time.tm_hour - 1

            install_duration = settings.get('installDuration')
            if install_duration is None:
                self.install_duration = 3600
            else:
                hr_min = install_duration.split(':')
                self.install_duration = int(hr_min[0]) * 3600 + int(hr_min[1]) * 60

            category = settings.get('category')
            if category is None:
                self.category = ''
            else:
                self.category = category

            print "Configurations:\ndisabled: %s\ndayOfWeek: %s\nstartTime: %s\ndownloadTime: %s\ninstallDuration: %s\ncategory: %s\n" % (self.disabled, ','.join([str(dow) for dow in self.day_of_week]), str(self.start_time.tm_hour), str(self.download_time), str(self.install_duration), self.category)

    def enable(self):
        pass

    def disable(self):
        pass

    def _checkOnly(self):
        pass

    def _setBlacklist(self):
        pass

    def _securityUpdate(self):
        pass

    def _setPeriodic(self):
        pass

    def _sendMail(self):
        pass

############################################################
#	UbuntuPatching
############################################################
class UbuntuPatching(AbstractPatching):
    def __init__(self, settings):
        super(UbuntuPatching,self).__init__(settings)
        self.clean_cmd = 'apt-get clean'
        self.check_cmd = 'apt-get -s upgrade'
        self.download_cmd = 'apt-get -d -y install'
        self.patch_cmd = 'apt-get -y install'
        self.status_cmd = 'apt-cache show'
        waagent.Run('grep "-security" /etc/apt/sources.list | sudo grep -v "#" > /etc/apt/security.sources.list')
        self.security_update_download_cmd = self.download_cmd + ' -o Dir::Etc::SourceList=/etc/apt/security.sources.list'

    def check(self):
        """
        Check valid upgrades,
        Return the package list to download & upgrade
        """
        retcode,output = waagent.RunGetOutput(self.check_cmd)
        if retcode > 0:
            print "Failed to check valid upgrades"
        start = output.find('The following packages will be upgraded')
        if start == -1:
            print "No package to upgrade"
            sys.exit(0)
        start = output.find('\n', start)
        end = output.find('upgraded', start)
        output = re.split(r'\s+', output[start:end].strip())
        output.pop()
        self.to_download = output

    def clean(self):
        retcode,output = waagent.RunGetOutput(self.clean_cmd)
        if retcode > 0:
            print "Failed to erase downloaded archive files"

    def download(self):
        start_download_time = time.time()
        self.check()
        self.clean()
        for package_to_download in self.to_download:
            if self.category == 'Important':
                download_cmd = self.security_update_download_cmd
            else:
                download_cmd = self.download_cmd
            retcode = waagent.Run(download_cmd + ' ' + package_to_download)
            if retcode > 0:
                print "Failed to download the package: " + package_to_download
                continue
            self.downloaded.append(package_to_download)
            current_download_time = time.time()
            if current_download_time - start_download_time > self.download_duration:
                break
        f = open('/run/package.downloaded', 'w')
        for package_downloaded in self.downloaded:
            self.to_download.remove(package_downloaded)
            f.write(package_downloaded + '\n')
        f.close()        

    def patch(self):
        start_patch_time = time.time()
        f = open('/run/package.downloaded', 'r')
        self.to_patch = [package_downloaded.strip() for package_downloaded in f.readlines()]
        f.close()
        for package_to_patch in self.to_patch:
            retcode = waagent.Run(self.patch_cmd + ' ' + package_to_patch)
            if retcode > 0:
                print "Failed to patch the package:" + package_to_patch
                continue
            self.patched.append(package_to_patch)
            current_patch_time = time.time()
            if current_patch_time - start_patch_time > self.install_duration:
                break
        f = open('/run/package.patched', 'w')
        for package_patched in self.patched:
            self.to_patch.remove(package_patched)
            f.write(package_patched + '\n')
        f.close()

    def report(self):
        status = {}
        package_patched = 'update-manager-core'
        status[package_patched] = {}
        retcode,output = waagent.RunGetOutput(self.status_cmd + ' ' + package_patched)
        output = output.split('\n\n')[0]
        print output

    def set_download_cron(self):
        if self.download_time == -1:
            hr = '23'
            dow = ','.join([str(day - 1) for day in self.day_of_week])
        else:
            hr = str(self.download_time)
            dow = ','.join([str(day) for day in self.day_of_week])
        contents = waagent.GetFileContents(self.crontab)
        script_file = os.path.realpath(__file__)
        [script_dir, script_file] = script_file.split('OSPatching/')
        new_line = '\n' + ' '.join(['*/1', hr, '* *', dow, 'root cd', script_dir + 'OSPatching', '&& python', script_file, '-download']) + '\n'
        old_line_end = 'azure-linux-extensions/OSPatching && python installer/handler.py -download'
        waagent.ReplaceFileContentsAtomic(self.crontab, "\n".join(filter(lambda a: old_line_end not in a, waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def set_patch_cron(self):
        contents = waagent.GetFileContents(self.crontab)
        script_file = os.path.realpath(__file__)
        [script_dir, script_file] = script_file.split('OSPatching/')
        hr = str(self.start_time.tm_hour)
        dow = ','.join([str(day) for day in self.day_of_week])
        new_line = '\n' + ' '.join(['*/1', hr, '* *', dow, 'root cd', script_dir + 'OSPatching', '&& python', script_file, '-patch']) + '\n'
        old_line_end = 'azure-linux-extensions/OSPatching && python installer/handler.py -patch'
        waagent.ReplaceFileContentsAtomic(self.crontab, "\n".join(filter(lambda a: old_line_end not in a, waagent.GetFileContents(self.crontab).split('\n'))) + new_line)

    def restart_cron(self):
        retcode,output = waagent.RunGetOutput(self.cron_restart_cmd)
        if retcode > 0:
            print output

    def enable(self):
        self.report()
        if self.disabled == 'false':
            self.set_download_cron()
            self.set_patch_cron()
            self.restart_cron()
        else:
            print "the disabled option in configuration is set to true, can not enable OSPatching"
        
    def disable(self):
        pass

############################################################
#	redhatPatching
############################################################
class redhatPatching(AbstractPatching):
    def __init__(self):
        super(redhatPatching,self).__init__()
        self.yum_cron_configfile = '/etc/sysconfig/yum-cron'
        
    def enable(self):
        #self._install()

        #mail = 'g.bin.xia@gmail.com'
        #self._sendMail(mail)

        #self._securityUpdate()

        #self._checkOnly(valid='no')

        #self._setBlacklist(['kernel*', 'php*'])

        self._setPeriodic(1)

        # Enable the automatic updates
        retcode,output = waagent.RunGetOutput('service yum-cron restart')
        if retcode > 0:
            waagent.Error(output)

        # Enable the daemon at boot time
        retcode,output = waagent.RunGetOutput('chkconfig yum-cron on')
        if retcode > 0:
            waagent.Error(output)

    def _install(self):
        retcode,output = waagent.RunGetOutput('yum -y install yum-cron')
        if retcode > 0:
            waagent.Error(output)

    def _checkOnly(self,valid='no'):
        contents = waagent.GetFileContents(self.yum_cron_configfile)
        start = contents.find('\nCHECK_ONLY=') + 1
        end = contents.find('\n',start)
        waagent.SetFileContents(self.yum_cron_configfile, contents[0:start] + 'CHECK_ONLY=' + valid + contents[end:None])

    def _setBlacklist(self, packageList):
        contents = waagent.GetFileContents(self.yum_cron_configfile)
        start = contents.find('\nYUM_PARAMETER=') + 1
        end = contents.find('\n',start)
        parameter = ' '.join(['-x ' + package for package in packageList])
        waagent.SetFileContents(self.yum_cron_configfile, contents[0:start] + 'YUM_PARAMETER="' + parameter + '"' + contents[end:None])

    def _securityUpdate(self):
        # Install the yum-plugin-security package to enable "yum --security update" commond
        retcode,output = waagent.RunGetOutput('yum -y install yum-plugin-security')
        retcode,output = waagent.RunGetOutput('yum --security update')

    def _setPeriodic(self, upgrade_periodic=1):
        contents = waagent.GetFileContents(self.yum_cron_configfile)
        start = contents.find('\nDAYS_OF_WEEK')
        if start > -1:
            start = start + 1
        else:
            start = contents.find('\n#DAYS_OF_WEEK') + 1
        end = contents.find('\n',start)
        # default is everyday
        periodic = '0123456'
        if upgrade_periodic == 7:
            periodic = '0'
        waagent.SetFileContents(self.yum_cron_configfile, contents[0:start] + 'DAYS_OF_WEEK="' + periodic + '"' + contents[end:None])

    def _sendMail(self,mail=''):
        contents = waagent.GetFileContents(self.yum_cron_configfile)
        start = contents.find('\nMAILTO=') + 1
        end = contents.find('\n',start)
        waagent.SetFileContents(self.yum_cron_configfile, contents[0:start] + 'MAILTO=' + mail + contents[end:None])
    

############################################################
#	centosPatching
############################################################
class centosPatching(redhatPatching):
    def __init__(self):
        super(centosPatching,self).__init__()

############################################################
#	SuSEPatching
############################################################
class SuSEPatching(AbstractPatching):
    def __init__(self):
        super(SuSEPatching,self).__init__()
        self.patch_cmd = 'zypper --non-interactive patch --auto-agree-with-licenses --with-interactive'
        self.cron_restart_cmd = 'service cron restart'
        self.cron_chkconfig_cmd = 'chkconfig cron on'
        self.crontab = '/etc/crontab'
        self.patching_cron = '/tmp/patching_cron'

    def enable(self):
        self._install()
        self._setPeriodic(1)

        #mail = 'g.bin.xia@gmail.com'
        #self._sendMail(mail)

        #self._securityUpdate()

        #self._checkOnly(valid='yes')

        #self._setBlacklist(['kernel*', 'php*'])

        retcode,output = waagent.RunGetOutput(self.cron_restart_cmd)
        if retcode > 0:
            waagent.Error(output)

        retcode,output = waagent.RunGetOutput(self.cron_chkconfig_cmd)
        if retcode > 0:
            waagent.Error(output)
        
    def _install(self):
        waagent.SetFileContents(self.patching_cron, self.patch_cmd)

    def _checkOnly(self,valid='no'):
        pass

    def _setBlacklist(self, packageList):
        pass
        
    def _securityUpdate(self):
        pass

    def _setPeriodic(self, upgrade_periodic=1):
        periodic_dict = {1:'/etc/cron.daily', 7:'/etc/cron.weekly', 30:'/etc/cron.monthly'}
        for cron_dir in periodic_dict.values():
            periodic_file = os.path.join(cron_dir, os.path.basename(self.patching_cron))
            if os.path.exists(periodic_file):
                os.remove(periodic_file)
        retcode,output = waagent.RunGetOutput(' '.join(['cp', self.patching_cron, periodic_dict[upgrade_periodic]]))

    def _sendMail(self,mail=''):
        contents = waagent.GetFileContents(self.crontab)
        start = contents.find('\nMAILTO=') + 1
        end = contents.find('\n',start)
        waagent.SetFileContents(self.crontab, contents[0:start] + 'MAILTO=' + mail + contents[end:None])

###########################################################
# END PATCHING CLASS DEFS
###########################################################

###########################################################
# BEGIN FUNCTION DEFS
###########################################################

def install():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Install','Installed','0', 'Install Succeeded')

def enable():
    #hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    #hutil.do_parse_context('Install')
    try:
        #protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        MyPatching.enable()
    except Exception, e:
        print "Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc())
        #hutil.error("Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        #hutil.do_exit(1, 'Enable','error','0', 'Enable failed.')

def download():
    MyPatching.download()

def patch():
    MyPatching.patch()

def uninstall():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Disable')
    hutil.do_exit(0,'Disable','success','0', 'Disable Succeeded')

def update():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Upadate')
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')
    
def modify_file(filename, src, dst):
    """
      Modify the configuration file using regular expression.
      src should be regular expression.
    """
    fileContents = waagent.GetFileContents(filename)
    pattern = re.compile(src)
    newFileContents = pattern.sub(dst, fileContents)
    waagent.SetFileContents(filename, newFileContents)

def GetMyPatching(settings, patching_class_name=''):
    """
    Return MyPatching object.
    NOTE: Logging is not initialized at this point.
    """
    if patching_class_name == '':
        if 'Linux' in platform.system():
            Distro=waagent.DistInfo()[0]
        else : # I know this is not Linux!
            if 'FreeBSD' in platform.system():
                Distro=platform.system()
        Distro=Distro.strip('"')
        Distro=Distro.strip(' ')
        patching_class_name=Distro+'Patching'
    else:
        Distro=patching_class_name
    if not globals().has_key(patching_class_name):
        print Distro+' is not a supported distribution.'
        return None
    return globals()[patching_class_name](settings)

###########################################################
# END FUNCTION DEFS
###########################################################

def main():
    global MyPatching
    MyPatching=GetMyPatching(settings = protect_settings)
    if MyPatching == None :
        sys.exit(1)
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
        elif re.match("^([-/]*)(download)", a):
            download()
        elif re.match("^([-/]*)(patch)", a):
            patch()


if __name__ == '__main__' :
    main()
