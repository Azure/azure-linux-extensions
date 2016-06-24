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
import urllib2
import urlparse
import datetime
import math


def main():
    ticks = 635798839149570996
    
    commandStartTime = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds = ticks/10)
    utcNow = datetime.datetime.utcnow()
    timespan = utcNow-commandStartTime
    
    print(str(timespan.total_seconds()))
    total_span_in_seconds = timespan.days * 24 * 60 * 60 + timespan.seconds
    print(str(total_span_in_seconds))

if __name__ == '__main__' :
    main()
