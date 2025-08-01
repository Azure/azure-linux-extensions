import base64
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback

from Common import *

from .redhatPatching import redhatPatching


class azurelinuxPatching(redhatPatching):
    def __init__(self,logger,distro_info):
        super(azurelinuxPatching,self).__init__(logger,distro_info)
        self.logger = logger
        self.min_version_online_encryption = '3.0'
        self.support_online_encryption = self.validate_online_encryption_support()
        self.grub_cfg_paths = [
            ("/boot/grub2/grub.cfg", "/boot/grub2/grubenv")
        ]

    def pack_initial_root_fs(self):
        self.command_executor.ExecuteInBash('dracut -f -v --regenerate-all', True)

    def add_kernelopts(self, args_to_add):
        self.add_args_to_default_grub(args_to_add)
        grub_cfg_paths = filter(lambda path_pair: os.path.exists(path_pair[0]) and os.path.exists(path_pair[1]), self.grub_cfg_paths)

        for grub_cfg_path, grub_env_path in grub_cfg_paths:
            for arg in args_to_add:
                self.command_executor.ExecuteInBash("grubby --args {0} --update-kernel ALL -c {1} --env={2}".format(arg, grub_cfg_path, grub_env_path))

    def install_cryptsetup(self):
        packages = ['cryptsetup']
        
        # Check each package individually
        packages_to_install = []
        for package in packages:
            check_command = "rpm -q " + package
            # rpm -q returns 0 (success) when package is installed
            if self.command_executor.Execute(check_command) != 0:
                packages_to_install.append(package)
        
        if packages_to_install:
            package_list = " ".join(packages_to_install)
            install_command = "tdnf install -y " + package_list
            
            # Execute the install command with a timeout
            return_code = self.command_executor.Execute(install_command, timeout=100)
            
            # Check for timeout error (-9 indicates timeout)
            if return_code == -9:
                msg = "Command: tdnf install timed out. Make sure tdnf is configured correctly and there are no network problems."
                self.logger.log(msg, level='error')
                raise Exception(msg)
            
            return return_code
        
        return 0

    def install_extras(self):
        packages = [
            'cryptsetup',
            'lsscsi',
            'psmisc',
            'lvm2',
            'uuid',
            'at',
            'patch',
            'procps-ng',
            'util-linux'
        ]

        # Modify the package list based on conditions
        if self.support_online_encryption:
            packages.append('nvme-cli')
            packages = [pkg for pkg in packages if pkg not in ['psmisc', 'uuid', 'at', 'patch', 'procps-ng']]
        
        # Check each package individually to handle partial installations
        packages_to_install = []
        for package in packages:
            check_command = "rpm -q " + package
            # rpm -q returns 0 (success) when package is installed
            if self.command_executor.Execute(check_command) != 0:
                packages_to_install.append(package)
        
        if packages_to_install:
            packages_to_install_str = " ".join(packages_to_install)
            install_command = "tdnf install -y " + packages_to_install_str
            
            # Execute the installation command
            self.command_executor.Execute(install_command)