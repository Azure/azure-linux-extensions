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
#
# Requires Python 2.7+
#
class CommonVariables:
    azure_path = 'main/azure'
    utils_path_name = 'Utils'
    extension_name = 'VMBackupForLinuxExtension'
    extension_version = "0.1.0.1"
    extension_type = extension_name
    extension_media_link = 'https://andliu.blob.core.windows.net/extensions/' + extension_name + '-' + str(extension_version) + '.zip'
    extension_label = 'Windows Azure VMBackup Extension for Linux IaaS'
    extension_description = extension_label
    object_str = 'objectStr'
    logs_blob_uri = 'logsBlobUri'
    status_blob_uri = 'statusBlobUri'
    commandStartTimeUTCTicks = "commandStartTimeUTCTicks"
    task_id = 'taskId'
    command_to_execute = 'commandToExecute'
    iaas_vmbackup_command = 'snapshot'
    iaas_install_command = 'install'
    locale = 'locale'

    """
    error code definitions
    """
    success = 1
    error_parameter = 11
    error_12 = 12
    error_wrong_time = 13
    error_same_taskid = 14
    error_http_failure = 15
    error_upload_status_blob = 16
    error = 2
