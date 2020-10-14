#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os

def is_systemd():
    """
    Check if the system is using systemd
    """

    check_systemd = os.system("pidof systemd 1>/dev/null 2>&1")
    return check_systemd == 0


def is_arc_installed():
    """
    Check if the system is an on prem machine running Arc
    """
    # Using systemctl to check this since Arc only supports VM that have systemd
    check_arc = os.system("systemctl status himdsd 1>/dev/null 2>&1")
    return check_arc == 0


def get_arc_endpoint():
    """
    Find the endpoint for arc Hybrid IMDS
    """
    endpoint_filepath = "/lib/systemd/system.conf.d/azcmagent.conf"
    with open(endpoint_filepath, "r") as f:
        data = f.read()
    endpoint = data.split("\"IMDS_ENDPOINT=")[1].split("\"\n")[0]

    return endpoint