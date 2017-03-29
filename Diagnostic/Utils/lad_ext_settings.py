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
        self._syslog_enabled = None

    def log_protected_settings_keys(self, logger_log, logger_err):
        """
        Log some protected settings information. Keys only for credentials and both key/value for known public
        values (e.g., storageAccountEndPoint). This was introduced to help ourselves find any misconfiguration
        issues related to the storageAccountEndPoint easier.
        :param logger_log: Normal logging function (e.g., hutil.log)
        :param logger_err: Error logging function (e.g., hutil.error)
        :return: None
        """
        try:
            msg = "Keys in privateSettings (and some non-secret values): "
            first = True
            for key in self._protected_settings:
                if first:
                    first = False
                else:
                    msg += ", "
                msg += key
                if key == 'storageAccountEndPoint':
                    msg += ":" + self._protected_settings[key]
            logger_log(msg)
        except Exception as e:
            logger_err("Failed to log keys in privateSettings. Error:{0}\n"
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

    def get_syslog_config(self):
        """
        Get syslog config from LAD extension settings.
        First look up 'ladCfg' section's 'syslogCfg' and use it. If none, then use 'syslogCfg' at the top level
        of public settings. Base64-encoded rsyslogd conf content is currently supported for 'syslogCfg' in either
        section.
        :return: rsyslogd configuration content string (base64-decoded 'syslogCfg' setting)
        """
        syslog_cfg = ''
        lad_cfg = self.read_public_config('ladCfg')
        encoded_syslog_cfg = LadUtil.getDiagnosticsMonitorConfigurationElement(lad_cfg, 'syslogCfg')
        if not encoded_syslog_cfg:
            encoded_syslog_cfg = self.read_public_config('syslogCfg')
        if encoded_syslog_cfg:
            syslog_cfg = base64.b64decode(encoded_syslog_cfg)
        return syslog_cfg

    def get_file_monitoring_config(self):
        """
        Get rsyslog file monitoring (imfile module) config from LAD extension settings.
        First look up 'ladCfg' and use it if one is there. If not, then get 'fileCfg' at the top level
        of public settings.
        :return: List of dictionaries specifying files to monitor and Azure table names for the destinations
        of the monitored files. E.g.:
        [
          {"file":"/var/log/a.log", "table":"aLog"},
          {"file":"/var/log/b.log", "table":"bLog"}
        ]
        """
        lad_cfg = self.read_public_config('ladCfg')
        file_cfg = LadUtil.getFileCfgFromLadCfg(lad_cfg)
        if not file_cfg:
            file_cfg = self.read_public_config('fileCfg')
        return file_cfg

    def get_mdsd_cfg(self):
        """
        Get 'mdsdCfg' setting from the LAD public settings. Since it's base64-encoded, decode it for returning.
        :return: Base64-decoded 'mdsdCfg' LAD public setting. '' if not present.
        """
        mdsd_cfg_str = self.read_public_config('mdsdCfg')
        if mdsd_cfg_str:
            mdsd_cfg_str = base64.b64decode(mdsd_cfg_str)
        return mdsd_cfg_str

    def get_lad30_syslogEvents_setting(self):
        """
        Get 'ladCfg/syslogEvents' setting from LAD 3.0 public settings.
        :return: A dictionary of syslog facility and minSeverity to monitor/ Refer to README.md for more details.
        """
        return LadUtil.getDiagnosticsMonitorConfigurationElement(self.read_public_config('ladCfg'), 'syslogEvents')

    def get_lad30_fileLogs_setting(self):
        """
        Get 'fileLogs' setting from LAD 3.0 public settings.
        :return: List of dictionaries specifying file to monitor and Azure table name for
        destinations of the monitored file. Refer to README.md for more details
        """
        return self.read_public_config('fileLogs')

    def is_syslog_enabled(self):
        """
        Check if syslog is enabled in the LAD settings ('enableSyslog' setting)
        :rtype: bool
        :return: True if so. False otherwise.
        """
        if self._syslog_enabled is None:
            # 'enableSyslog' is to be used for consistency, but we've had 'EnableSyslog' all the time,
            # so accommodate it.
            enable_syslog_setting = self.read_public_config('enableSyslog') if self.has_public_config('enableSyslog') \
                                    else self.read_public_config('EnableSyslog')
            if not enable_syslog_setting:
                self._syslog_enabled = True  # Default is enabled when the setting is not specified
            elif isinstance(enable_syslog_setting, bool):
                self._syslog_enabled = enable_syslog_setting
            elif not isinstance(enable_syslog_setting, basestring):
                self._syslog_enabled = True  # Ignore non-bool, non-string setting and default it to true
            else:  # string case.
                self._syslog_enabled = self.read_public_config('enableSyslog').lower() != 'false' \
                                       and self.read_public_config('EnableSyslog').lower() != 'false'
        return self._syslog_enabled