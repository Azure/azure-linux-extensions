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
        return self.disk_util.encryption_environment.resume_daemon_status_file_path

    def begin_resume(self):
        mapper_path = os.path.join(CommonVariables.dev_mapper_root, self.crypt_item.mapper_name)
        if not os.path.exists(mapper_path):
            self.logger.log("{0} does not exist. Exiting Resume encryption daemon.".format(mapper_path))
            return

        if not self.disk_util.luks_check_reencryption(self.crypt_item.dev_path, self.crypt_item.luks_header_path):
            self.logger.log("{0} is not in reencryption.".format(mapper_path))
            return

        resume_cmd = "cryptsetup reencrypt --resume-only --active-name {0} --header {1} -d {2} --resilience journal".format(self.crypt_item.mapper_name, self.crypt_item.luks_header_path or self.crypt_item.dev_path, self.bek_file_path)
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
                    self.hutil.do_status_report(operation='DataCopy',
                                                status=CommonVariables.extension_success_status,
                                                status_code=str(CommonVariables.success),
                                                message=full_message)
            if child.returncode == CommonVariables.success:
                message = "Background encryption finished for {0}".format(self.crypt_item.dev_path)
                self.hutil.do_status_report(operation='DataCopy',
                                            status=CommonVariables.extension_success_status,
                                            status_code=str(CommonVariables.success),
                                            message=message)
        # Let's clean up after ourselves
        os.remove(status_file_path)
