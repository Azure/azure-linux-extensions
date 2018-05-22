#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import base64
import copy
import json
import traceback
import Utils.LadDiagnosticUtil as LadUtil
import Utils.XmlUtil as XmlUtil


class ExtSettings(object):
    """
    Wrapper class around any generic Azure extension settings Json objects.
    TODO This class may better go to some place else (e.g., HandlerUtil.py).
    """
    def __init__(self, handler_settings):
        """
        Constructor
        :param handler_settings: Json object (dictionary) decoded from the extension settings Json string.
        """
        self._handler_settings = handler_settings if handler_settings else {}
        public_settings = self._handler_settings.get('publicSettings')
        self._public_settings = public_settings if public_settings else {}
        protected_settings = self._handler_settings.get('protectedSettings')
        self._protected_settings = protected_settings if protected_settings else {}

    def get_handler_settings(self):
        """
        Hanlder settings (Json dictionary) getter
        :return: Handler settings Json object
        """
        return self._handler_settings

    def has_public_config(self, key):
        """
        Determine if a particular setting is present in the public config
        :param str key: The setting to look for
        :return: True if the setting is present (regardless of its value)
        :rtype: bool
        """
        return key in self._public_settings

    def read_public_config(self, key):
        """
        Return the value of a particular public config setting
        :param str key: The setting to retrieve
        :return: The value of the setting if present; an empty string (*not* None) if the setting is not present
        :rtype: str
        """
        if key in self._public_settings:
            return self._public_settings[key]
        return ''

    def read_protected_config(self, key):
        """
        Return the value of a particular protected config setting
        :param str key: The setting to retrive
        :return: The value of the setting if present; an empty string (*not* None) if the setting is not present
        :rtype: str
        """
        if key in self._protected_settings:
            return self._protected_settings[key]
        return ''


class LadExtSettings(ExtSettings):
    """
    LAD-specific extension settings object that supports LAD-specific member functions
    """
    def __init__(self, handler_settings):
        super(LadExtSettings, self).__init__(handler_settings)

    def redacted_handler_settings(self):
        """
        Get handler settings in string after redacting secrets (for diagnostic purpose w/ Geneva telemetry)
        :rtype: str
        :return: String for the handler settings JSON object with secrets redacted.
        """
        # The logic below could have been a general-purpose JSON tree walker, but since the specific
        # knowledge of where secrets are needs be applied anyway, it's coded for this specific schema anyway.
        # Secrets are stored only in the following paths: .storageAccountSasToken, and .sinksConfig.sink[].sasURL.
        # LAD 2.3 used to support storageAccountKey; although LAD 3.0 does not support it, some users might mistakenly
        # supply it. We redact it, if present, even though we're going to throw an error later on; the protected
        # settings are logged before we inspect them to pull out the credentials.

        # Get and work on a copy of the handler settings dict. Note that it must be a deep copy!
        # dict(self.get_handler_settings()) doesn't work!
        handler_settings = copy.deepcopy(self.get_handler_settings())
        protected_settings = handler_settings['protectedSettings']
        if protected_settings:
            if 'storageAccountSasToken' in protected_settings:
                protected_settings['storageAccountSasToken'] = 'REDACTED_SECRET'
            if 'storageAccountKey' in protected_settings:
                protected_settings['storageAccountKey'] = 'REDACTED_SECRET'
            if 'sinksConfig' in protected_settings and 'sink' in protected_settings['sinksConfig']:
                for each_sink_dict in protected_settings['sinksConfig']['sink']:
                    if 'sasURL' in each_sink_dict:
                        each_sink_dict['sasURL'] = 'REDACTED_SECRET'
        return json.dumps(handler_settings, sort_keys=True)

    def log_ext_settings_with_secrets_redacted(self, logger_log, logger_err):
        """
        Log entire extension settings with secrets redacted. This was introduced to help ourselves find any
        misconfiguration issues related to the storageAccountEndPoint easier, and later extended to log all
        extension settings with secrets redacted, for better diagnostics.
        :param logger_log: Normal logging function (e.g., hutil.log)
        :param logger_err: Error logging function (e.g., hutil.error)
        :return: None
        """
        try:
            msg = "LAD settings with secrets redacted: {0}".format(
                self.redacted_handler_settings())
            logger_log(msg)
        except Exception as e:
            logger_err("Failed to log LAD settings with secrets redacted. Error:{0}\n"
                       "Stacktrace: {1}".format(e, traceback.format_exc()))

    def get_resource_id(self):
        """
        Try to get resourceId from LadCfg. If not present, try to fetch from xmlCfg.
        """
        lad_cfg = self.read_public_config('ladCfg')
        resource_id = LadUtil.getResourceIdFromLadCfg(lad_cfg)
        if not resource_id:
            encoded_xml_cfg = self.read_public_config('xmlCfg').strip()
            if encoded_xml_cfg:
                xml_cfg = base64.b64decode(encoded_xml_cfg)
                resource_id = XmlUtil.getXmlValue(XmlUtil.createElement(xml_cfg),
                                                  'diagnosticMonitorConfiguration/metrics', 'resourceId')
                # Azure portal uses xmlCfg which contains WadCfg which is pascal case
                # Currently we will support both casing and deprecate one later
                if not resource_id:
                    resource_id = XmlUtil.getXmlValue(XmlUtil.createElement(xml_cfg),
                                                      'DiagnosticMonitorConfiguration/Metrics', 'resourceId')
        return resource_id

    def get_syslogEvents_setting(self):
        """
        Get 'ladCfg/syslogEvents' setting from LAD 3.0 public settings.
        :return: A dictionary of syslog facility and minSeverity to monitor/ Refer to README.md for more details.
        """
        return LadUtil.getDiagnosticsMonitorConfigurationElement(self.read_public_config('ladCfg'), 'syslogEvents')

    def get_fileLogs_setting(self):
        """
        Get 'fileLogs' setting from LAD 3.0 public settings.
        :return: List of dictionaries specifying file to monitor and Azure table name for
        destinations of the monitored file. Refer to README.md for more details
        """
        return self.read_public_config('fileLogs')

    def get_mdsd_trace_option(self):
        """
        Return traceFlags, if any, from public config
        :rtype: str
        :return: trace flags or an empty string
        """
        flags = self.read_public_config('traceFlags')
        if flags:
            return " -T {0}".format(flags)
        else:
            return ""
