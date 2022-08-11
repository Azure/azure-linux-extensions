import subprocess
import json
import os
import os.path
import re
from subprocess import Popen
import traceback
import glob

from io import open
from Common import CommonVariables, LvmItem, DeviceItem
from CommandExecutor import CommandExecutor, ProcessCommunicator

class DiskUtil(object):
    os_disk_lvm = None
    sles_cache = {}

    def __init__(self):
        self.ide_class_id = "{32412632-86cb-44a2-9b5c-50d1417354f5}"
        self.vmbus_sys_path = '/sys/bus/vmbus/devices'

        self.command_executor = CommandExecutor()

        self._LUN_PREFIX = "lun"
        self._SCSI_PREFIX = "scsi"

        self.unencrypted_data_disks = []

    def get_osmapper_path(self):
        return os.path.join(CommonVariables.dev_mapper_root, CommonVariables.osmapper_name)

    def _isnumeric(self, chars):
        try:
            int(chars)
            return True
        except ValueError:
            return False

    def get_device_path(self, dev_name):
        device_path = None
        # ensure the use of a string representation for python2 + python3 compat
        dev_name = str(dev_name)

        if os.path.exists("/dev/" + dev_name):
            device_path = "/dev/" + dev_name
        elif os.path.exists(os.path.join(CommonVariables.dev_mapper_root, dev_name)):
            device_path = os.path.join(CommonVariables.dev_mapper_root, dev_name)

        return device_path

    def get_device_id(self, dev_path):
        udev_cmd = "udevadm info -a -p $(udevadm info -q path -n {0}) | grep device_id".format(dev_path)
        proc_comm = ProcessCommunicator()
        self.command_executor.ExecuteInBash(udev_cmd, communicator=proc_comm, suppress_logging=True)
        match = re.findall(r'"{(.*)}"', proc_comm.stdout.strip())
        return match[0] if match else ""

    def get_azure_devices(self):
        device_names = []
        blk_items = []

        # Get all IDE devices
        ide_devices = self.get_ide_devices()
        for ide_device in ide_devices:
            device_names.append("/dev/" + ide_device)

        # get all SCSI 0 devices
        device_names += self.get_scsi0_device_names()

        # some machines use special root dir symlinks instead of scsi0 symlinks
        device_names += self.get_azure_symlinks_root_dir_devices()

        # let us do some de-duping
        device_names_realpaths = set(map(os.path.realpath, device_names))

        for device_path in device_names_realpaths:
            current_blk_items = self.get_device_items(device_path)
            for current_blk_item in current_blk_items:
                blk_items.append(current_blk_item)

        return blk_items

    def unescape(self, s):
        # python2 and python3+ compatible function for converting escaped unicode bytes to unicode string
        if s is None:
            return None
        else:
            # decode unicode escape sequences, encode back to latin1, then decode all as
            return s.decode('unicode-escape').encode('latin1').decode('utf-8')

    def get_mount_items(self):
        items = []
        # open as binary in both python2 and python3+ prior to unescape
        for line in open('/proc/mounts', 'rb'):
            mp_line = self.unescape(line)
            mp_list = [s for s in mp_line.split()]
            mp_item = {
                "src": mp_list[0],
                "dest": mp_list[1],
                "fs": mp_list[2]
            }
            items.append(mp_item)
        return items

    def get_encryption_status(self):
        encryption_status = {
            "data": "NotEncrypted",
            "os": "NotEncrypted"
        }

        mount_items = self.get_mount_items()
        device_items = self.get_device_items(None)
        device_items_dict = dict([(device_item.mount_point, device_item) for device_item in device_items])

        os_drive_encrypted = False
        data_drives_found = False
        all_data_drives_encrypted = True

        if self.is_os_disk_lvm(device_items):
            grep_result = self.command_executor.ExecuteInBash('pvdisplay | grep {0}'.format(self.get_osmapper_path()),
                                                              suppress_logging=True)
            if grep_result == 0 and not os.path.exists('/volumes.lvm'):
                os_drive_encrypted = True

        special_azure_devices_to_skip = self.get_azure_devices()
        for mount_item in mount_items:
            device_item = device_items_dict.get(mount_item["dest"])

            if device_item is not None and \
               mount_item["fs"] in CommonVariables.format_supported_file_systems and \
               self.is_data_disk(device_item, special_azure_devices_to_skip):
                data_drives_found = True

                if not device_item.type == "crypt":
                    print("Data volume {0} is mounted from {1} but not encrypted".format(mount_item["dest"], mount_item["src"]))
                    all_data_drives_encrypted = False
                    self.unencrypted_data_disks += str(mount_item["src"])

            if mount_item["dest"] == "/" and \
               not self.is_os_disk_lvm(device_items) and \
               CommonVariables.dev_mapper_root in mount_item["src"] or \
               "/dev/dm" in mount_item["src"]:
                print("Non-LVM OS volume {0} is mounted from {1} and encrypted".format(mount_item["dest"], mount_item["src"]))
                os_drive_encrypted = True

        if not data_drives_found:
            encryption_status["data"] = "NotMounted"
        elif all_data_drives_encrypted:
            encryption_status["data"] = "Encrypted"
        if os_drive_encrypted:
            encryption_status["os"] = "Encrypted"

        return encryption_status

    def get_device_items(self, dev_path):
        if dev_path is None:
            lsblk_command = 'lsblk -b -n -P -o NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN'
        else:
            lsblk_command = 'lsblk -b -n -P -o NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN ' + dev_path

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(lsblk_command, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)

        device_items = []
        lvm_items = self.get_lvm_items()
        for line in proc_comm.stdout.splitlines():
            if line:
                device_item = DeviceItem()

                for disk_info_property in str(line).split():
                    property_item_pair = disk_info_property.split('=')
                    if property_item_pair[0] == 'SIZE':
                        device_item.size = int(property_item_pair[1].strip('"'))

                    if property_item_pair[0] == 'NAME':
                        device_item.name = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'TYPE':
                        device_item.type = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'FSTYPE':
                        device_item.file_system = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'MOUNTPOINT':
                        device_item.mount_point = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'LABEL':
                        device_item.label = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'UUID':
                        device_item.uuid = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'MODEL':
                        device_item.model = property_item_pair[1].strip('"')

                    if property_item_pair[0] == 'MAJ:MIN':
                        device_item.majmin = property_item_pair[1].strip('"')

                device_item.device_id = self.get_device_id(self.get_device_path(device_item.name))

                if device_item.type is None:
                    device_item.type = ''

                if device_item.type.lower() == 'lvm':
                    for lvm_item in lvm_items:
                        majmin = lvm_item.lv_kernel_major + ':' + lvm_item.lv_kernel_minor

                        if majmin == device_item.majmin:
                            device_item.name = lvm_item.vg_name + '/' + lvm_item.lv_name

                device_items.append(device_item)

        return device_items

    def get_lvm_items(self):
        lvs_command = 'lvs --noheadings --nameprefixes --unquoted -o lv_name,vg_name,lv_kernel_major,lv_kernel_minor'
        proc_comm = ProcessCommunicator()

        try:
            self.command_executor.Execute(lvs_command, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)
        except Exception:
            return []  # return empty list on non-lvm systems that do not have lvs

        lvm_items = []

        for line in proc_comm.stdout.splitlines():
            if not line:
                continue

            lvm_item = LvmItem()

            for pair in str(line).strip().split():
                if len(pair.split('=')) != 2:
                    continue

                key, value = pair.split('=')

                if key == 'LVM2_LV_NAME':
                    lvm_item.lv_name = value

                if key == 'LVM2_VG_NAME':
                    lvm_item.vg_name = value

                if key == 'LVM2_LV_KERNEL_MAJOR':
                    lvm_item.lv_kernel_major = value

                if key == 'LVM2_LV_KERNEL_MINOR':
                    lvm_item.lv_kernel_minor = value

            lvm_items.append(lvm_item)

        return lvm_items

    def is_os_disk_lvm(self, device_items):
        if DiskUtil.os_disk_lvm is not None:
            return DiskUtil.os_disk_lvm

        #device_items = self.get_device_items(None)

        if not any([item.type.lower() == 'lvm' for item in device_items]):
            DiskUtil.os_disk_lvm = False
            return False

        try:
            # if VM supports online encryption
            if os.system("lsblk -o TYPE,MOUNTPOINT | grep lvm | grep -q '/$'") == 0:
                DiskUtil.os_disk_lvm = True
                return True
        except:
            print("Warning: Exception logged while checking LVM with online encryption scenario.")

        lvm_items = [item for item in self.get_lvm_items() if item.vg_name == "rootvg"]

        current_lv_names = set([item.lv_name for item in lvm_items])

        DiskUtil.os_disk_lvm = False

        if 'homelv' in current_lv_names and 'rootlv' in current_lv_names:
            DiskUtil.os_disk_lvm = True

        return DiskUtil.os_disk_lvm

    def is_data_disk(self, device_item, special_azure_devices_to_skip):
        # Skipping Root disk
        if device_item.device_id.startswith('00000000-0000'):
            return False
        # Skipping Resource Disk. Not considered a "data disk" exactly (is not attached via portal and we have a separate code path for encrypting it)
        if device_item.device_id.startswith('00000000-0001'):
            return False
        # BEK VOLUME
        if device_item.file_system == "vfat" and device_item.label.lower() == "bek":
            return False

        # We let the caller specify a list of devices to skip. Usually its just a list of IDE devices.
        # IDE devices (in Gen 1) include Resource disk and BEK VOLUME. This check works pretty wel in Gen 1, but not in Gen 2.
        for azure_blk_item in special_azure_devices_to_skip:
            if azure_blk_item.name == device_item.name:
                if device_item.name:
                    print(device_item.name + "is a special azure device to skip.")
                return False

        return True

    def get_azure_symlinks_root_dir_devices(self):
        """
        There is a directory that provide helpful persistent symlinks to important devices
        We scrape the directory to identify "special" devices that should not be
        encrypted along with other data disks
        """

        devices = []

        azure_links_dir = CommonVariables.azure_symlinks_dir
        if os.path.exists(azure_links_dir):
            known_special_device_names = ["root", "resource"]
            for device_name in known_special_device_names:
                full_device_path = os.path.join(azure_links_dir, device_name)
                if os.path.exists(full_device_path):
                    devices.append(full_device_path)

        azure_links_dir = CommonVariables.cloud_symlinks_dir
        if os.path.exists(azure_links_dir):
            known_special_device_names = ["azure_root", "azure_resource"]
            for device_name in known_special_device_names:
                full_device_path = os.path.join(azure_links_dir, device_name)
                if os.path.exists(full_device_path):
                    devices.append(full_device_path)

        return devices

    def get_ide_devices(self):
        """
        this only return the device names of the ide.
        """
        ide_devices = []
        for vmbus in os.listdir(self.vmbus_sys_path):
            f = open('%s/%s/%s' % (self.vmbus_sys_path, vmbus, 'class_id'), 'r')
            class_id = f.read()
            f.close()
            if class_id.strip() == self.ide_class_id:
                device_sdx_path = self.find_block_sdx_path(vmbus)
                ide_devices.append(device_sdx_path)
        return ide_devices

    def get_scsi0_device_names(self):
        """
        gen2 equivalent of get_ide_devices()
        """
        devices = []
        azure_links_dir = CommonVariables.azure_symlinks_dir
        scsi0_dir = os.path.join(azure_links_dir, self._SCSI_PREFIX + "0")

        if not os.path.exists(scsi0_dir):
            return devices

        for symlink in os.listdir(scsi0_dir):
            if symlink.startswith(self._LUN_PREFIX) and self._isnumeric(symlink[3:]):
                devices.append(os.path.join(scsi0_dir, symlink))

        return devices

    def find_block_sdx_path(self, vmbus):
        device = None
        for root, dirs, files in os.walk(os.path.join(self.vmbus_sys_path, vmbus)):
            if root.endswith("/block"):
                device = dirs[0]
            else:  # older distros
                for d in dirs:
                    if ':' in d and "block" == d.split(':')[0]:
                        device = d.split(':')[1]
                        break
        return device

