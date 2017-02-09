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

import traceback


class LadExtSettings:
    """
    Wrapper class around LAD's extension settings Json objects.
    """
    def __init__(self, handler_settings):
        self._handler_settings = handler_settings if handler_settings else {}
        public_settings = self._handler_settings.get('publicSettings')
        self._public_settings = public_settings if public_settings else {}
        protected_settings = self._handler_settings.get('protectedSettings')
        self._protected_settings = protected_settings if protected_settings else {}

    def get_handler_settings(self):
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
        if key in self._protected_settings:
            return self._protected_settings[key]
        return ''

    def log_protected_settings_keys(self, logger_log, logger_err):
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

