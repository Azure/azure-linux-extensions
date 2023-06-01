#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2019 Microsoft Corporation
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
import shlex
import subprocess
import os
import os.path
from time import sleep
from threading import Lock

from Common import CommonVariables


class OnlineEncryptionResumer:
    def __init__(self, crypt_item, disk_util, bek_file_path, logger, hutil):
        self.STATUS_INTERVAL = 15
        self.crypt_item = crypt_item
        self.disk_util = disk_util
        self.bek_file_path = bek_file_path
        self.logger = logger
        self.hutil = hutil

    def _get_status_file(self):
        return self.disk_util.encryption_environment.resume_daemon_status_file_path + self.crypt_item.mapper_name + ".txt"

    def update_log(self, msg, lock):
        if lock is None:
            self.logger.log(msg)
            return
        else:
            lock.acquire()
            self.logger.log(msg)
            lock.release()

    def begin_resume(self, log_status=True, lock=None, import_token = False, public_setting=None):
        self.logger.log("Starting background resume encrytion for device: " + self.crypt_item.dev_path)
        mapper_path = os.path.join(CommonVariables.dev_mapper_root, self.crypt_item.mapper_name)
        if not os.path.exists(mapper_path):
            self.update_log("{0} does not exist. Exiting Resume encryption daemon.".format(mapper_path), lock)
            return

        if not self.disk_util.luks_check_reencryption(self.crypt_item.dev_path, self.crypt_item.luks_header_path):
            self.update_log("{0} is not in reencryption.".format(mapper_path), lock)
            return

        resume_cmd = None
        if self.crypt_item.luks_header_path is None:
            resume_cmd = "cryptsetup reencrypt --resume-only --active-name {0} -d {1}".format(self.crypt_item.mapper_name, self.bek_file_path)
        else:
            resume_cmd = "cryptsetup reencrypt --resume-only --active-name {0} --header {1} -d {2} --resilience journal".format(self.crypt_item.mapper_name, self.crypt_item.luks_header_path, self.bek_file_path)
        status_file_path = self._get_status_file()
        with open(status_file_path, "wb") as status_file_write:
            args = shlex.split(resume_cmd)

            # Run resume command but redirect it's stdout to a file
            child = subprocess.Popen(args, stdout=status_file_write, stderr=subprocess.PIPE)

            status_message = None
            while child.poll() is None:
                sleep(self.STATUS_INTERVAL)
                with open(status_file_path, "r") as status_file_read:
                    lines = status_file_read.readlines()
                    if len(lines) > 0:
                        status_message = lines[-1].strip()
                if status_message:
                    full_message = "Background encrypting {0} - {1}".format(self.crypt_item.dev_path, status_message)
                    if log_status:
                        self.hutil.do_status_report(operation='DataCopy',
                                                    status=CommonVariables.extension_success_status,
                                                    status_code=str(CommonVariables.success),
                                                    message=full_message)
                    else:
                        self.update_log(full_message, lock)
            if child.returncode == CommonVariables.success:
                message = "Background encryption finished for {0}".format(self.crypt_item.dev_path)
                if import_token and public_setting:
                    self.update_log("Background token update to device {0}".format(self.crypt_item.dev_path),lock)
                    self.disk_util.import_token(device_path=self.crypt_item.dev_path,
                                       passphrase_file=self.bek_file_path,
                                       public_settings=public_setting)
                if log_status:
                    self.hutil.do_status_report(operation='DataCopy',
                                                status=CommonVariables.extension_success_status,
                                                status_code=str(CommonVariables.success),
                                                message=message)
                else:
                    self.update_log(message, lock)
        # Let's clean up after ourselves
        os.remove(status_file_path)
