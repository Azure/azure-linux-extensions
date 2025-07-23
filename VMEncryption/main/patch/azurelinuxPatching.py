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
        package_list = " ".join(packages)
        
        # Log the start of the installation process
        self.logger.log(f"Checking if {package_list} is already installed.")
        
        # Check if the package is already installed
        check_command = f"rpm -q {package_list}"
        if self.command_executor.Execute(check_command):
            self.logger.log(f"{package_list} not installed, proceeding with installation.")
            
            install_command = f"tdnf install -y {package_list}"
            self.logger.log(f"Running command: {install_command} with a timeout of 100 seconds.")
            
            # Execute the install command with a timeout
            return_code = self.command_executor.Execute(install_command, timeout=100)
            
            # Check for timeout error (-9 indicates timeout)
            if return_code == -9:
                msg = "Command: tdnf install timed out. Make sure tdnf is configured correctly and there are no network problems."
                self.logger.log(msg, level='error')
                raise Exception(msg)
            
            self.logger.log(f"Installation command completed with return code: {return_code}")
            return return_code
        
        else:
            self.logger.log(f"{package_list} is already installed.")
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
        self.logger.log("Starting installation of extra packages.")

        # Modify the package list based on conditions
        if self.support_online_encryption:
            self.logger.log("Online encryption is supported; modifying package list.")
            packages.append('nvme-cli')
            packages = [pkg for pkg in packages if pkg not in ['psmisc', 'uuid', 'at', 'patch', 'procps-ng']]
        
        package_list = " ".join(packages)
        self.logger.log(f"Final package list for installation: {package_list}")
        
        # Check if the packages are already installed
        check_command = f"rpm -q {package_list}"
        if self.command_executor.Execute(check_command):
            self.logger.log(f"Packages not fully installed, proceeding with installation: {package_list}")
            
            install_command = f"tdnf install -y {package_list}"
            self.logger.log(f"Running command: {install_command}")
            
            # Execute the installation command
            return_code = self.command_executor.Execute(install_command)
            
            self.logger.log(f"Installation of packages completed with return code: {return_code}")
        else:
            self.logger.log(f"All required packages are already installed: {package_list}")
        
        self.logger.log("Completed installation of extra packages.")