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

class RsyslogConfig:
    """
    Utility class for obtaining rsyslog configurations for omazuremds output module and imfile input module
    based on the LAD 3.0 syslog config schema. Diagnostic/README.md will include documentation
    for the LAD 3.0 syslog config schema.
    """

    def __init__(self, syslogEvents, syslogCfg, fileLogs):
        """
        Constructor to receive/store necessary LAD settings for the desired configuration generation.

        :param syslogEvents: LAD 3.0 "ladCfg" - "syslogEvents" JSON object, or a False object if it's not given
                             in the extension settings. An example is as follows:

                             "ladCfg": {
                                 "syslogEvents" : {
                                     "syslogEventConfiguration": {
                                         "facilityName1": "minSeverity1",
                                         "facilityName2": "minSeverity2"
                                     }
                                 }
                             }

                             Only the JSON object corresponding to "syslogEvents" key should be passed.

                             facilityName1/2 is a syslog facility name (e.g., "LOG_USER", "LOG_LOCAL0").
                             minSeverity1/2 is a syslog severity level (e.g., "LOG_ERR", "LOG_CRIT") or "NONE".
                                 "NONE" means no logs from the facility will be captured (thus it's equivalent to
                                  not specifying the facility at all).

        :param syslogCfg: LAD 3.0 "syslogCfg" JSON object, or a False object if it's not given in the ext settings.
                          An example is as follows:

                          "syslogCfg": [
                              {
                                  "facility": "LOG_USER",
                                  "minSeverity": "LOG_ERR",
                                  "table": "SyslogUserErrorEvents"
                              },
                              {
                                  "facility": "LOG_LOCAL0",
                                  "minSeverity": "LOG_CRIT",
                                  "table": "SyslogLocal0CritEvents"
                              }
                          ]

                          Only the JSON array corresponding to "syslogCfg" key should be passed.

                          "facility" and "minSeverity" are self-explanatory. "table" is for the Azure storage table
                          into which the matching syslog events will be placed.

        :param fileLogs: LAD 3.0 "fileLogs" JSON object, or a False object if it's not given in the ext settings.
                         An example is as follows:

                         "fileLogs": {
                             "fileLogConfiguration": [
                                 {
                                     "file": "/var/log/mydaemonlog",
                                     "table": "MyDaemonEvents"
                                 },
                                 {
                                     "file": "/var/log/myotherdaemonelog",
                                     "table": "MyOtherDaemonEvents"
                                 }
                             ]
                         }

                         Only the JSON array corresponding to "fileLogConfiguration" key should be passed.

                         "file" is the full path of the log file to be watched and captured. "table" is for the
                         Azure storage table into which the lines of the watched file will be placed (one row per line).
        """

        self._syslogEvents = syslogEvents
        self._syslogCfg = syslogCfg
        self._fileLogs = fileLogs

    def get_omazuremds_config(self, legacy=False):
        """
        Get omazuremds rsyslog output module config that corresponds to the syslogEvents and/or the syslogCfg JSON
        object given in the construction parameters.

        :param legacy: A boolean indicating whether to get omazuremds config for rsyslog 5/7 (legacy rsyslog config)
        :return: omazuremds rsyslog output module config string that should be saved to a file and placed in
                 /etc/rsyslog.d/ directory
        """
        pass

    def get_imfile_config(self):
        """
        Get imfile rsyslog input module config that corresponds to the fileLogs JSON object given in the construction
        parameters.
        :return: imfile rsyslog input module config string that should be saved to a file and placed in
                 /etc/rsyslog.d/ directory
        """
        pass