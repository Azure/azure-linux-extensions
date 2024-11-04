#!/usr/bin/env python
#
# VM Backup extension
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

import time
import sys
from NodeBasedConstants import NodeBasedConstants

# Compatibility for Python 2 and 3
try:
    import requests  # For HTTP requests
except ImportError:
    print("The 'requests' library is required. Install it with 'pip install requests'.")
    sys.exit(1)

URL = NodeBasedConstants.GET_SNAPSHOT_REQUESTS_URI
INTERVAL = NodeBasedConstants.SERVICE_POLLING_INTERVAL_IN_SECS

IsExecuting = False

def upon_new_requests():
    print("Executing the current request.")

def check_for_new_requests():
    global IsExecuting
    IsExecuting = True
    try:
        response = requests.get(URL)
        if response.status_code == 200:
            print("Success: {0} - {1}".format(response.status_code, response.text[:100]))
            upon_new_requests()
        else:
            print("Failed: {0} - {1}".format(response.status_code, response.reason))
    except requests.exceptions.RequestException as e:
        print("Error during request: {0}".format(e))
    finally:
        IsExecuting = False  # Set back to False after execution

def main():
    print("Starting Polling...")
    while True:
        if not IsExecuting:  # Only fetch if not already executing
            check_for_new_requests()
        print("Waiting for {0} seconds...".format(INTERVAL))
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
