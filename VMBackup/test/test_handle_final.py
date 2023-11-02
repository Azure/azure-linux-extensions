#!/usr/bin/env python
#
#CustomScript extension
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
import string
import subprocess
import sys
import imp
import shlex
import traceback
#import urllib2
#import urlparse
import datetime
import math
current = os.path.dirname(os.path.realpath(__file__))

# Getting the parent directory name
# where the current directory is present.
parent = os.path.dirname(current)
 
# adding the parent directory to 
# the sys.path.
sys.path.append(parent)
#print(parent)
sys.path.append('..')
main = os.path.join(parent,'main')
#print(main)
sys.path.append(main)
from main.Utils import HandlerUtil 
from patch import GetMyPatching
from backuplogger import Backuplogger
from common import CommonVariables
from Utils import SizeCalculation
from mock import MagicMock


def main():
    ticks = 635798839149570996
    
    commandStartTime = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds = ticks/10)
    utcNow = datetime.datetime.utcnow()
    timespan = utcNow-commandStartTime
    
    print(str(timespan.total_seconds()))
    total_span_in_seconds = timespan.days * 24 * 60 * 60 + timespan.seconds
    print(str(total_span_in_seconds))

    # run a test for exclude disk scenario
    excludeDisk()

def excludeDisk():
    Log = MagicMock()
    Error = MagicMock()
    hutil = HandlerUtil.HandlerUtility(Log, Error, CommonVariables.extension_name)
    backup_logger = Backuplogger(hutil)
    MyPatching, patch_class_name, orig_distro = GetMyPatching(backup_logger)
    hutil.patching = MyPatching
    para_parser = MagicMock()
    para_parser.includedDisks = {"dataDiskLunList":[-1],"isAnyDirectDriveDiskIncluded":None,"isAnyDiskExcluded":True,"isAnyWADiskIncluded":None,"isOSDiskIncluded":False,"isVmgsBlobIncluded":None}
    para_parser.includeLunList = para_parser.includedDisks["dataDiskLunList"]
    sizeCalculation = SizeCalculation.SizeCalculation(patching = MyPatching , hutil = hutil, logger = backup_logger, para_parser = para_parser)
    total_used_size,size_calculation_failed = sizeCalculation.get_total_used_size()
    print(total_used_size)
    print(size_calculation_failed)



if __name__ == '__main__' :
    main()

