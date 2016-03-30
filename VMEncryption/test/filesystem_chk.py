#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2015 Microsoft Corporation
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
# Requires Python 2.7+
#

import array
import base64
import httplib
import imp
import json
import os
import os.path
import re
import errno
import shlex
import string
import subprocess
import sys
import io
import datetime
import time
import tempfile
import traceback
import urllib2
import urlparse
import uuid


def fillfile(path):
    write_str = '!' * 1023 + '\n'
    with open(path, "w") as f:
        for i in range(0,1024):
            f.write(write_str)
            f.flush()

def fill_file_system(mount_point):
    i = 0
    while True:
        try:
            file_path = os.path.join(mount_point, "file{0}".format(i))
            i+=1
            fillfile(file_path)
        except Exception as e:
            print e
            os.remove(file_path)

def check_file_system():
    pass
            
def main():
    for a in sys.argv[1:]:
        if re.match("^([-/]*)(fillfile)", a):
            mount_point = sys.argv[2]
            fill_file_system(mount_point)
        elif re.match("^([-/]*)(check)", a):
            check_file_system()

if __name__ == '__main__' :
    main()
