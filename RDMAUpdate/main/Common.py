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


class CommonVariables:
    azure_path = 'main/azure'
    utils_path_name = 'Utils'
    extension_name = 'RDMAUpdateForLinux'
    extension_version = "0.1.0.8"
    extension_type = extension_name
    extension_media_link = 'https://andliu.blob.core.windows.net/extensions/' + extension_name + '-' + str(extension_version) + '.zip'
    extension_label = 'Windows Azure RDMA Update Extension for Linux IaaS'
    extension_description = extension_label

    """
    configurations
    """
    wrapper_package_name = 'msft-rdma-drivers'

    """
    error code definitions
    """
    process_success = 0
    common_failed = 1
    install_hv_utils_failed = 2
    nd_driver_detect_error = 3
    driver_version_not_found = 4
    unknown_error = 5
    package_not_found = 6
    package_install_failed = 7

    """
    logs related
    """
    InfoLevel = 'Info'
    WarningLevel = 'Warning'
    ErrorLevel = 'Error'

    """
    check_rdma_result
    """
    UpToDate = 0
    OutOfDate = 1
    DriverVersionNotFound = 3
    Unknown = -1

