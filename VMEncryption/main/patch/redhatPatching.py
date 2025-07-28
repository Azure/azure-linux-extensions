#!/usr/bin/python
#
# Copyright 2015 Microsoft Corporation
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

import os
import os.path
import sys
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime
import subprocess
import inspect
import io
import filecmp

from .AbstractPatching import AbstractPatching
from Common import *
from CommandExecutor import *
from distutils.version import LooseVersion

class redhatPatching(AbstractPatching):
    def __init__(self, logger, distro_info):
        super(redhatPatching, self).__init__(distro_info)
        self.logger = logger
        self.command_executor = CommandExecutor(logger)
        self.distro_info = distro_info
        if distro_info[1].startswith("6."):
            self.base64_path = '/usr/bin/base64'
            self.bash_path = '/bin/bash'
            self.blkid_path = '/sbin/blkid'
            self.cat_path = '/bin/cat'
            self.cryptsetup_path = '/sbin/cryptsetup'
            self.dd_path = '/bin/dd'
            self.e2fsck_path = '/sbin/e2fsck'
            self.echo_path = '/bin/echo'
            self.getenforce_path = '/usr/sbin/getenforce'
            self.setenforce_path = '/usr/sbin/setenforce'
            self.lsblk_path = '/bin/lsblk' 
            self.lsscsi_path = '/usr/bin/lsscsi'
            self.mkdir_path = '/bin/mkdir'
            self.mount_path = '/bin/mount'
            self.openssl_path = '/usr/bin/openssl'
            self.resize2fs_path = '/sbin/resize2fs'
            self.touch_path = '/bin/touch'
            self.umount_path = '/bin/umount'
        else:
            self.base64_path = '/usr/bin/base64'
            self.bash_path = '/usr/bin/bash'
            self.blkid_path = '/usr/bin/blkid'
            self.cat_path = '/bin/cat'
            self.cryptsetup_path = '/usr/sbin/cryptsetup'
            self.dd_path = '/usr/bin/dd'
            self.e2fsck_path = '/sbin/e2fsck'
            self.echo_path = '/usr/bin/echo'
            self.getenforce_path = '/usr/sbin/getenforce'
            self.setenforce_path = '/usr/sbin/setenforce'
            self.lsblk_path = '/usr/bin/lsblk'
            self.lsscsi_path = '/usr/bin/lsscsi'
            self.mkdir_path = '/usr/bin/mkdir'
            self.mount_path = '/usr/bin/mount'
            self.openssl_path = '/usr/bin/openssl'
            self.resize2fs_path = '/sbin/resize2fs'
            self.touch_path = '/usr/bin/touch'
            self.umount_path = '/usr/bin/umount'
        self.min_version_online_encryption = '8.1'
        if type(self).__name__.startswith('redhat'):
            # Should not be called when actual instance is of subclass like oracle
            self.support_online_encryption = self.validate_online_encryption_support()
        self.grub_cfg_paths = [
            ("/boot/grub2/grub.cfg", "/boot/grub2/grubenv"),
            ("/boot/efi/EFI/redhat/grub.cfg", "/boot/efi/EFI/redhat/grubenv")
        ]

    def install_cryptsetup(self):
        if self.distro_info[1].startswith("6."):
            packages = ['cryptsetup-reencrypt']
        else:
            packages = ['cryptsetup']

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            return_code = self.command_executor.Execute("yum install -y " + " ".join(packages), timeout=100)
            if return_code == -9:
                msg = "Command: yum install timed out. Make sure yum is configured correctly and there are no network problems."
                raise Exception(msg)
            return return_code

    def install_extras(self):
        packages = ['cryptsetup',
                    'lsscsi',
                    'psmisc',
                    'lvm2',
                    'uuid',
                    'at',
                    'patch',
                    'procps-ng',
                    'util-linux']

        if self.distro_info[1].startswith("6."):
            packages.append('cryptsetup-reencrypt')
            packages.remove('cryptsetup')
            packages.remove('procps-ng')
            packages.remove('util-linux')

        if self.support_online_encryption:
            packages.append('nvme-cli')
            packages.remove('psmisc')
            packages.remove('uuid')
            packages.remove('at')
            packages.remove('patch')
            packages.remove('procps-ng')

        if self.command_executor.Execute("rpm -q " + " ".join(packages)):
            self.command_executor.Execute("yum install -y " + " ".join(packages))

    def update_prereq(self):
        if (self.distro_info[1].startswith('7.')):
            dracut_repack_needed = False

            if os.path.exists("/lib/dracut/modules.d/91lvm/"):
                # If 90lvm already exists 91lvm will cause problems, so remove it.
                if os.path.exists("/lib/dracut/modules.d/90lvm/"):
                    shutil.rmtree("/lib/dracut/modules.d/91lvm/")
                else:
                    os.rename("/lib/dracut/modules.d/91lvm/","/lib/dracut/modules.d/90lvm/")
                dracut_repack_needed = True

            if redhatPatching.is_old_patching_system():
                redhatPatching.remove_old_patching_system(self.logger, self.command_executor)
                dracut_repack_needed = True

            if os.path.exists("/lib/dracut/modules.d/91ade/"):
                shutil.rmtree("/lib/dracut/modules.d/91ade/")
                dracut_repack_needed = True

            if os.path.exists("/dev/mapper/osencrypt") and not os.path.exists("/lib/dracut/modules.d/91adeOnline/"):
                # Do not add 91ade module if 91adeOnline module is present
                #TODO: only do this if needed (if code and existing module are different)
                redhatPatching.add_91_ade_dracut_module(self.command_executor)
                dracut_repack_needed = True

            if dracut_repack_needed:
                self.command_executor.ExecuteInBash("/usr/sbin/dracut -f -v --kver `grubby --default-kernel | sed 's|/boot/vmlinuz-||g'`", True)

        self.update_crypt_parse_file()

    def update_crypt_parse_file(self, proc_comm=None):
        if proc_comm is None:
            proc_comm = ProcessCommunicator()
        crypt_parse_filename = 'parse-crypt-ade.sh'
        ade_dracut_modules_dir = '/lib/dracut/modules.d/91adeOnline'
        crypt_parse_file_dst = os.path.join(ade_dracut_modules_dir, crypt_parse_filename)
        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        ademoduledir = os.path.join(scriptdir, '../oscrypto/91adeOnline')
        crypt_parse_filename = 'parse-crypt-ade.sh'
        crypt_parse_file = os.path.join(ademoduledir, crypt_parse_filename)
        ade_dracut_modules_dir = '/lib/dracut/modules.d/91adeOnline'
        crypt_parse_file_dst = os.path.join(ade_dracut_modules_dir, crypt_parse_filename)

        if not os.path.exists(ade_dracut_modules_dir):
            self.logger.log("ADE online module not present. No need to update crypt parse script.")
            return

        if filecmp.cmp(crypt_parse_file, crypt_parse_file_dst, shallow=True):
            self.logger.log("ADE parse crypt script already updated.")
            return
        
        return_code = self.command_executor.ExecuteInBash('cat /etc/default/grub | grep -c rd.luks.ade.bootuuid', communicator=proc_comm)
        if return_code != 0:
            self.logger.log("ADE parameters not present in default grub. No need to update crypt parse script.")
            return

        if int(proc_comm.stdout.strip()) > 1:
            self.logger.log("Duplicate ADE parameter detected in deafult grub. Num occurences: " + proc_comm.stdout)
            try:
                self.logger.log("Updating parse crypt file.")
                shutil.copyfile(crypt_parse_file,crypt_parse_file_dst)
            except:
                pass
            self.logger.log("Regenerate initrd after parse crypt update.")
            self.pack_initial_root_fs()
            return

        self.logger.log("ADE parse crypt in expected state.")
        return

    @staticmethod
    def is_old_patching_system():
        # Execute unpatching commands only if all the three patch files are present.
        if os.path.exists("/lib/dracut/modules.d/90crypt/cryptroot-ask.sh.orig"):
            if os.path.exists("/lib/dracut/modules.d/90crypt/module-setup.sh.orig"):
                if os.path.exists("/lib/dracut/modules.d/90crypt/parse-crypt.sh.orig"):
                    return True
        return False

    @staticmethod
    def _append_contents_to_file(self, contents, path):
        # Python 3.x strings are Unicode by default and do not use decode
        if sys.version_info[0] < 3:
            if isinstance(contents, str):
                contents = contents.decode('utf-8')

        with io.open(path, 'a') as f:
            f.write(contents)

    @staticmethod
    def add_91_ade_dracut_module(command_executor):
        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        ademoduledir = os.path.join(scriptdir, '../oscrypto/91ade')
        dracutmodulesdir = '/lib/dracut/modules.d'
        udevaderulepath = os.path.join(dracutmodulesdir, '91ade/50-udev-ade.rules')

        proc_comm = ProcessCommunicator()

        command_executor.Execute('cp -r {0} /lib/dracut/modules.d/'.format(ademoduledir), True)

        crypt_cmd = "cryptsetup status osencrypt | grep device:"
        command_executor.ExecuteInBash(crypt_cmd, communicator=proc_comm, suppress_logging=True)
        matches = re.findall(r'device:(.*)', proc_comm.stdout)
        if not matches:
            raise Exception("Could not find device in cryptsetup output")
        root_device = matches[0].strip()

        udevadm_cmd = "udevadm info --attribute-walk --name={0}".format(root_device)
        command_executor.Execute(command_to_execute=udevadm_cmd, raise_exception_on_failure=True, communicator=proc_comm)
        matches = re.findall(r'ATTR{partition}=="(.*)"', proc_comm.stdout)
        if not matches:
            raise Exception("Could not parse ATTR{partition} from udevadm info")
        partition = matches[0]
        sed_cmd = 'sed -i.bak s/ENCRYPTED_DISK_PARTITION/{0}/ "{1}"'.format(partition, udevaderulepath)
        command_executor.Execute(command_to_execute=sed_cmd, raise_exception_on_failure=True)
        sed_grub_cmd = "sed -i.bak '/osencrypt-locked/d' /etc/crypttab"
        command_executor.Execute(command_to_execute=sed_grub_cmd, raise_exception_on_failure=True)


    @staticmethod
    def remove_old_patching_system(logger, command_executor):
        logger.log("Removing patches and recreating initrd image")

        command_executor.Execute('mv /lib/dracut/modules.d/90crypt/cryptroot-ask.sh.orig /lib/dracut/modules.d/90crypt/cryptroot-ask.sh', False)
        command_executor.Execute('mv /lib/dracut/modules.d/90crypt/module-setup.sh.orig /lib/dracut/modules.d/90crypt/module-setup.sh', False)
        command_executor.Execute('mv /lib/dracut/modules.d/90crypt/parse-crypt.sh.orig /lib/dracut/modules.d/90crypt/parse-crypt.sh', False)
        
        sed_grub_cmd = "sed -i.bak '/rd.luks.uuid=osencrypt/d' /etc/default/grub"
        command_executor.Execute(sed_grub_cmd)
    
        redhatPatching.append_contents_to_file('\nGRUB_CMDLINE_LINUX+=" rd.debug"\n', 
                                               '/etc/default/grub')

        redhatPatching.append_contents_to_file('osencrypt UUID=osencrypt-locked none discard,header=/osluksheader\n',
                                               '/etc/crypttab')

        command_executor.Execute('/usr/sbin/dracut -f -v', True)
        command_executor.Execute('grub2-mkconfig -o /boot/grub2/grub.cfg', True)

    def add_kernelopts(self, args_to_add):
        self.add_args_to_default_grub(args_to_add)
        
        grub_cfg_paths = filter(lambda path_pair: os.path.exists(path_pair[0]) and os.path.exists(path_pair[1]), self.grub_cfg_paths)

        extra_parameters = ""
        if type(self).__name__.startswith('redhat'):
            # Should not be called when actual instance is of subclass like oracle
            if LooseVersion(self.distro_info[1]) >= LooseVersion('9.3'):
                extra_parameters = extra_parameters + "--update-bls-cmdline"
            else:
                installed_package = self.get_installed_package_version('grub2-tools')
                if installed_package is not None:
                    extract_version = self.extract_version(installed_package)
                    self.logger.log("grub tool Version: {}".format(extract_version))
                    if extract_version is not None and LooseVersion(extract_version) >= LooseVersion('2.06.69'):
                        extra_parameters = extra_parameters + "--update-bls-cmdline"
                    
        self.logger.log("Extra Parameters for grub2-mkconfig {}".format(extra_parameters))
        
        for grub_cfg_path, grub_env_path in grub_cfg_paths:
            self.command_executor.ExecuteInBash('grub2-mkconfig -o {0} {1}'.format(grub_cfg_path, extra_parameters), True)

    def get_installed_package_version(self, package_name):
        try:
            proc_comm = ProcessCommunicator()
            result = self.command_executor.Execute("rpm -q {}".format(package_name), communicator=proc_comm)
            if result == 0:
                return proc_comm.stdout.strip()
            else:
                self.logger.log("Package: {} not found.".format(package_name))
                return None
        except Exception as e:
            self.logger.log("Exception: {}".format(str(e)))
            return None

    def extract_version(self, package_string):
        match = re.search(r'(\d+\.\d+-\d+)', package_string)
        if match:
            return match.group(1).replace('-','.')
        return None
    
    def pack_initial_root_fs(self):
        self.command_executor.ExecuteInBash('dracut -f -v --regenerate-all', True)

    def install_and_enable_ade_online_enc(self, root_partuuid, boot_uuid, rootfs_disk, is_os_disk_lvm=False):
        # Copy the 91adeOnline directory to dracut/modules.d
        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        ademoduledir = os.path.join(scriptdir, '../oscrypto/91adeOnline')
        self.command_executor.Execute('cp -r {0} /lib/dracut/modules.d/'.format(ademoduledir), True)

        # Change config so that dracut will force add the dm_crypt kernel module
        self.append_contents_to_file('\nadd_drivers+=" dm_crypt "\n',
                                      '/etc/dracut.conf.d/ade.conf')

        # Add the new kernel param
        additional_params = ["rd.luks.ade.partuuid={0}".format(root_partuuid),
                             "rd.luks.ade.bootuuid={0}".format(boot_uuid),
                             "rd.debug"]
        self.add_kernelopts(additional_params)

        # For clarity after reboot, we should also add the correct info to crypttab
        entry = 'osencrypt /dev/disk/by-partuuid/{0} /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,discard,header=/boot/luks/osluksheader'.format(root_partuuid)
        self.append_contents_to_file(entry, '/etc/crypttab')

        if is_os_disk_lvm:
            #Add the plain os disk base to the "LVM Reject list" and add osencrypt device to the "Accept list"
            self.append_contents_to_file('\ndevices { filter = ["a|osencrypt|", "r|' + root_partuuid + '|"] }\n', '/etc/lvm/lvm.conf')
            # Force dracut to include LVM and Crypt modules
            self.append_contents_to_file('\nadd_dracutmodules+=" crypt lvm "\n',
                                          '/etc/dracut.conf.d/ade.conf')
        else:
            self.append_contents_to_file('\nadd_dracutmodules+=" crypt "\n',
                                          '/etc/dracut.conf.d/ade.conf')
            self.add_kernelopts(["root=/dev/mapper/osencrypt"])