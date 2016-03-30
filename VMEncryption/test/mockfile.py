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

def fillsize():
    write_str = "!" * 1023 + '\n'
    write_str_len=len(write_str)
    output_path = sys.argv[2]
    size = int(sys.argv[3])
    written_size=0
    with open(output_path, "w") as f:
        while written_size<=size:
            try:
                f.write(write_str)
                f.flush()
                written_size+=write_str_len
            except IOError as err:
                if err.errno == errno.ENOSPC:
                    write_str_len = len(write_str)
                    if write_str_len > 1:
                        write_str = write_str[:write_str_len / 2]
                    else:
                        break
                else:
                    raise

def fillfile():
    write_str = "!" * 1023 + '\n'
    output_path = sys.argv[2]
    with open(output_path, "w") as f:
        while True:
            try:
                f.write(write_str)
                f.flush()
            except IOError as err:
                if err.errno == errno.ENOSPC:
                    write_str_len = len(write_str)
                    if write_str_len > 1:
                        write_str = write_str[:write_str_len / 2]
                    else:
                        break
                else:
                    raise

def check():
    write_str = "!" * 1023 + '\n'
    output_path = sys.argv[2]
    with open(output_path, "r") as f:
        read_str='\n'
        while read_str != "":
            read_str = f.readline()
            if(write_str != read_str):
                print("NOT EQUALS!!!")
            
def main():
    for a in sys.argv[1:]:
        if re.match("^([-/]*)(fillfile)", a):
            fillfile()
        elif re.match("^([-/]*)(check)", a):
            check()
        elif re.match("^([-/]*)(fillsize)", a):
            fillsize()

if __name__ == '__main__' :
    main()
