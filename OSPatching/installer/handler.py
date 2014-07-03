#!/usr/bin/env python
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
    def __init__(self):
        self.configFile = None

    def enable(self, settings):
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
    def __init__(self):
        self.unattended_upgrade_configfile = '/etc/apt/apt.conf.d/50unattended-upgrades'
        self.periodic_configfile = '/etc/apt/apt.conf.d/10periodic'
        self.upgrade_log_dir = '/var/log/unattended-upgrades/'
        self.mail = 'g.bin.xia@gmail.com'

    def enable(self):
        #self._sendMail()

        #self._securityUpdate()

        #retcode,output = self._checkOnly()
        #if (retcode == 0):
        #    print output

        #self._setBlacklist(['vim', 'libc6'])

        self._setPeriodic(1)

    def _checkOnly(self):
        return waagent.RunGetOutput('apt-get -s upgrade')

    def _setBlacklist(self, packageList):
        contents = waagent.GetFileContents(self.unattended_upgrade_configfile)
        start = contents.find('Unattended-Upgrade::Package-Blacklist {')
        start = contents.find('\n',start)
        end = contents.find('};',start)
        lines = contents[start:end].split('\n')
        waagent.SetFileContents(self.unattended_upgrade_configfile, contents[0:start+1] + '\n'.join(['\t\"'+p+'\";' for p in packageList]) + contents[end-1:None])


    def _securityUpdate(self):
        contents = waagent.GetFileContents(self.unattended_upgrade_configfile)
        start = contents.find('Unattended-Upgrade::Allowed-Origins {')
        start = contents.find('\n',start)
        end = contents.find('};',start)
        lines = contents[start:end].split('\n')
        newlines = list()
        for line in lines:
            if 'security' in line.strip():
                line = line.lstrip('//')
            else:
                if line.strip() and (not line.strip().startswith('//')):
                    line = '//' + line
            newlines.append(line)
        waagent.SetFileContents(self.unattended_upgrade_configfile, contents[0:start] + '\n'.join(newlines) + contents[end:None])

    def _setPeriodic(self, upgrade_periodic):
        contents = 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Download-Upgradeable-Packages "1";\nAPT::Periodic::AutocleanInterval "7";\n'
        contents += 'APT::Periodic::Unattended-Upgrade "' + str(upgrade_periodic) + '";\n';
        waagent.SetFileContents(self.periodic_configfile, contents)

    def _sendMail(self):
        modify_file(self.unattended_upgrade_configfile, '(//)?Unattended-Upgrade::Mail ".*"', 'Unattended-Upgrade::Mail \"' + self.mail + '\"')
        retcode,output = waagent.RunGetOutput('apt-get install heirloom-mailx')
        if retcode > 0:
            waagent.Error(output)

############################################################
#	CentOSPatching
############################################################
class CentOSPatching(AbstractPatching):
    def __init__(self):
        pass

############################################################
#	OraclePatching
############################################################
class OraclePatching(CentOSPatching):
    def __init__(self):
        pass

############################################################
#	SuSEPatching
############################################################
class SuSEPatching(AbstractPatching):
    def __init__(self):
        pass



def main():
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
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0,'Install','Installed','0', 'Install Succeeded')

def enable():
    #hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    #hutil.do_parse_context('Install')
    try:
        #protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        global LinuxDistro
        LinuxDistro=waagent.DistInfo()[0]
        LinuxDistro=LinuxDistro.strip('"')
        LinuxDistro=LinuxDistro.strip(' ')
        patching_class_name=LinuxDistro+'Patching'
        if not globals().has_key(patching_class_name):
            print LinuxDistro+' is not a supported distribution.'
            sys.exit(1)
        MyPatching = globals()[patching_class_name]()
        MyPatching.enable()
    except Exception, e:
        print "Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc())
        #hutil.error("Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        #hutil.do_exit(1, 'Enable','error','0', 'Enable failed.')

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
    

if __name__ == '__main__' :
    main()
