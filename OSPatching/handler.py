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

from patch.patch import *

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

# protect_settings_disabled = {
#     "disabled":"true",
# }

# protect_settings = {
#     "disabled" : "false",
#     "dayOfWeek" : "Sunday|Monday|Wednesday|Thursday|Friday|Saturday",
#     "startTime" : "00:00",                                                            # UTC time
#     "category" : "Important",
#     "installDuration" : "00:30"                                                       # in 30 minute increments
# }
#####################################################################################

# Global variables definition
ExtensionShortName = 'OSPatching'

###########################################################
# BEGIN FUNCTION DEFS
###########################################################

def install():
    # hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    # hutil.do_parse_context('Uninstall')
    # hutil.do_exit(0,'Install','Installed','0', 'Install Succeeded')
    try:
        MyPatching.install()
    except Exception, e:
        print "Failed to install the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc())

def enable():
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context('Install')
    try:
        protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
        MyPatching.enable(protect_settings)
    except Exception, e:
        #print "Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc())
        hutil.error("Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable','error','0', 'Enable failed.')

def download():
    MyPatching.download()

def patch():
    MyPatching.patch()

def report():
    MyPatching.report()

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
    
# Define the function in case waagent(<2.0.4) doesn't have DistInfo()
def DistInfo(fullname=0):
    if 'FreeBSD' in platform.system():
        release = re.sub('\-.*\Z', '', str(platform.release()))
        distinfo = ['FreeBSD', release]
        return distinfo
    if 'linux_distribution' in dir(platform):
        distinfo = list(platform.linux_distribution(full_distribution_name=fullname))
        distinfo[0] = distinfo[0].strip() # remove trailing whitespace in distro name
        return distinfo
    else:
        return platform.dist()

def GetMyPatching(patching_class_name=''):
    """
    Return MyPatching object.
    NOTE: Logging is not initialized at this point.
    """
    if patching_class_name == '':
        if 'Linux' in platform.system():
            Distro=DistInfo()[0]
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
    return globals()[patching_class_name]()

###########################################################
# END FUNCTION DEFS
###########################################################

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName)) 

    global MyPatching
    MyPatching=GetMyPatching()
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
        elif re.match("^([-/]*)(report)", a):
            report()


if __name__ == '__main__' :
    main()
