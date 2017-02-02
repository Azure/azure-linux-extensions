#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
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

import datetime
import urllib2
import time
import traceback


def get_imds_data(node, json=True):
    """
    Query IMDS endpoint for instance metadata and return the response as a Json string.
    """
    if not node:
        return None
    if node[0] != '/':
        node = '/' + node
    imds_url = 'http://169.254.169.254{0}{1}'.format(node, '?format=json' if json else '')
    imds_headers = {'Metadata': 'True'}
    req = urllib2.Request(url=imds_url, headers=imds_headers)
    resp = urllib2.urlopen(req)
    data = resp.read()
    data_str = data.decode('utf-8')
    return data_str


class ImdsLogger:
    """
    Periodically probes IMDS endpoint and log the result as WALA events.
    """

    def __init__(self, ext_name, ext_ver, ext_op_type, ext_event_logger, ext_logger=None,
                 imds_data_getter=get_imds_data, logging_interval_in_minutes=60):
        self._ext_name = ext_name
        self._ext_ver = ext_ver
        self._ext_op_type = ext_op_type
        self._ext_logger = ext_logger  # E.g., hutil.log
        self._ext_event_logger = ext_event_logger  # E.g., waagent.AddExtensionEvent
        self._last_log_time = None
        self._imds_data_getter = imds_data_getter
        self._logging_interval = datetime.timedelta(minutes=logging_interval_in_minutes)

    def log_imds_data_if_right_time(self, log_as_ext_event=False):
        now = datetime.datetime.now()
        not_yet = self._last_log_time and now < self._last_log_time + self._logging_interval
        if not_yet:
            return

        try:
            imds_data = self._imds_data_getter('/metadata/latest/instance/')
        except Exception as e:
            self._ext_logger('Exception occurred while getting IMDS data: {0}\n'
                             'stacktrace: {1}').format(e, traceback.format_exc())
            imds_data = '{0}'.format(e)

        msg = 'IMDS instance data = {0}'.format(imds_data)
        if log_as_ext_event:
            self._ext_event_logger(name=self._ext_name,
                                   op=self._ext_op_type,
                                   isSuccess=True,
                                   version=self._ext_ver,
                                   message=msg)
        if self._ext_logger:
            self._ext_logger(msg)
        self._last_log_time = now


if __name__ == '__main__':

    def fake_get_imds_data(node, json=True):
        result = 'fake_get_imds_data(node="{0}", json="{1}")'.format(node, json)
        print result
        return result


    def default_ext_logger(msg):
        print 'default_ext_logger(msg="{0}")'.format(msg)


    def default_ext_event_logger(*args, **kwargs):
        print 'default_ext_event_logger(*args, **kwargs)'
        print 'args:'
        for arg in args:
            print arg
        print 'kwargs:'
        for k in kwargs:
            print('"{0}"="{1}"'.format(k, kwargs[k]))


    imds_logger = ImdsLogger('Microsoft.OSTCExtensions.LinuxDiagnostic', '2.3.9021', 'Heartbeat',
                             ext_logger=default_ext_logger, ext_event_logger=default_ext_event_logger,
                             imds_data_getter=fake_get_imds_data, logging_interval_in_minutes=1)
    start_time = datetime.datetime.now()
    done = False
    while not done:
        now = datetime.datetime.now()
        print 'Test loop iteration starting at {0}'.format(now)
        imds_logger.log_imds_data_if_right_time()
        if now >= start_time + datetime.timedelta(minutes=2):
            done = True
        else:
            print 'Sleeping 10 seconds'
            time.sleep(10)
