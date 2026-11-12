import os
import os.path
import sys
try:
    import imp as imp
except ImportError:
    import importlib as imp
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import base64
import json
import re
import tempfile
import time
from Utils.DiskUtil import DiskUtil
from Utils.ResourceDiskUtil import ResourceDiskUtil
import Utils.HandlerUtil
import traceback
import subprocess
import shlex
from common import CommonVariables

AZURE_DISK_SYMLINK_DIR = '/dev/disk/azure'
SYS_BLOCK_DIR = '/sys/block'
PROC_MOUNTS_FILE = '/proc/self/mounts'
AZURE_NVME_REMOTE_DISK_MODEL = 'MSFT NVMe Accelerator v1.0'
TEMP_DISK_WARNING_FILE = 'DATALOSS_WARNING_README.txt'
DF_TIMEOUT_IN_SECONDS = 300

# One row of POSIX (df -P) output; mount points may contain spaces.
DF_LINE_REGEX = re.compile(r'^(?P<device>.+?)\s+(?P<size>-|\d+)\s+(?P<used>-|-?\d+)\s+(?P<available>-|-?\d+)\s+(?P<percent>-|\d+%)\s+(?P<mountpoint>/.*)$')

class SizeCalculation(object):

    def __init__(self,patching, hutil, logger,para_parser):
        self.patching = patching
        self.logger = logger
        self.hutil = hutil
        self.includedLunList = []
        self.file_systems_info = []
        self.non_physical_file_systems = ['fuse', 'nfs', 'cifs', 'overlay', 'aufs', 'lustre', 'secfs2', 'iso']
        self.known_fs = ['ext3', 'ext4', 'jfs', 'xfs', 'reiserfs', 'devtmpfs', 'tmpfs', 'rootfs', 'fuse', 'nfs', 'cifs', 'overlay', 'aufs', 'lustre', 'secfs2', 'zfs', 'btrfs', 'iso']
        self.isOnlyOSDiskBackupEnabled = False
        try:
            if(para_parser.customSettings != None and para_parser.customSettings != ''):
                self.logger.log('customSettings : ' + str(para_parser.customSettings))
                customSettings = json.loads(para_parser.customSettings)
                if("isOnlyOSDiskBackupEnabled" in customSettings):
                    self.isOnlyOSDiskBackupEnabled = customSettings["isOnlyOSDiskBackupEnabled"]
                    if(self.isOnlyOSDiskBackupEnabled == True):
                        Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("billingType","os disk")
                    else:
                        Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("billingType","none")
                self.logger.log("isOnlyOSDiskBackupEnabled : {0}".format(str(self.isOnlyOSDiskBackupEnabled)))
        except Exception as e:
            errMsg = 'Failed to serialize customSettings with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            self.isOnlyOSDiskBackupEnabled = False

        self.disksToBeIncluded = []
        self.root_devices = []
        self.root_mount_points = ['/' , '/boot/efi']
        self.os_disk_mount_points = ['/', '/boot', '/boot/efi']
        self.lsscsi_list = []
        self.output_lsblk = []
        self.pvs_output = []
        self.pvs_dict = {}
        self.lvs_output = []
        self.lv_segments = {}
        self.partial_logicalVolumeGroups = []
        self.counted_devices = set()

        self.devicesToInclude = [] #partitions to be included
        self.device_mount_points = []
        self.isAnyDiskExcluded = False
        self.LunListEmpty = False
        self.logicalVolume_to_bill = []
        self.sudo_off = 0 # run the commands using sudo
        if(para_parser.includedDisks != None and para_parser.includedDisks != '' and CommonVariables.isAnyDiskExcluded in para_parser.includedDisks.keys() and para_parser.includedDisks[CommonVariables.isAnyDiskExcluded] != None ):
            self.isAnyDiskExcluded = para_parser.includedDisks[CommonVariables.isAnyDiskExcluded]
            self.logger.log("isAnyDiskExcluded {0}".format(self.isAnyDiskExcluded))
        if( para_parser.includeLunList != None and para_parser.includeLunList != ''):
            self.includedLunList = para_parser.includeLunList
        self.logger.log("includedLunList {0}".format(self.includedLunList))
        if(self.includedLunList == None or len(self.includedLunList) == 0):
            self.LunListEmpty = True
            self.logger.log("As the LunList is empty including all disks")
    
    def get_lsscsi_list(self):
        command = "lsscsi"
        if (self.sudo_off == 0):
            command = "sudo " + command
        try:
            self.logger.log("executing command  {0}".format(command))
            self.lsscsi_list = (os.popen(command).read()).splitlines()
        except Exception as e:
            error_msg = "Failed to execute the command \"%s\" because of error %s , stack trace: %s" % (command, str(e), traceback.format_exc())
            self.logger.log(error_msg, True ,'Error')
            self.lsscsi_list = []

    def get_lsblk_list(self):
        try:
            self.output_lsblk = os.popen("lsblk -n --list --output name,mountpoint").read().strip().splitlines()
        except Exception as e:
            error_msg = "Failed to execute the command lsblk -n --list --output name,mountpoint because of error %s , stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(error_msg, True ,'Error')
            self.output_lsblk = []

    def get_pvs_list(self):
        try:
            command = "pvs --noheadings -o pv_name,vg_name"
            if (self.sudo_off == 0):
                command = "sudo " + command
            self.pvs_output = os.popen(command).read().strip().splitlines()
        except Exception as e:
            error_msg = "Failed to execute the command \"%s\" because of error %s , stack trace: %s" % (command, str(e), traceback.format_exc())
            self.logger.log(error_msg, True ,'Error')
            self.pvs_output = []

    def build_pvs_dict(self):
        '''
            Builds {volume group : [physical volumes]} from "pvs --noheadings -o pv_name,vg_name"
            Sample output:
              /dev/sda4  rootvg
              /dev/sdc1  datavg
              /dev/sdd          (physical volume which is not part of any volume group)
        '''
        self.pvs_dict = {}
        try:
            for pvs_item in self.pvs_output:
                pvs_item_split = pvs_item.strip().split()
                if(len(pvs_item_split) >= 2):
                    physicalVolume = pvs_item_split[0]
                    logicalVolumeGroup = pvs_item_split[1]
                    self.pvs_dict.setdefault(logicalVolumeGroup, []).append(physicalVolume)
            self.logger.log("The pvs_dict contains {0}".format(str(self.pvs_dict)))
        except Exception as e:
            errMsg = 'Failed to serialize pvs_output with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')

    @staticmethod
    def is_device_on_disk(device, disk):
        # True if device is the disk itself or one of its partitions (/dev/sdc1 on /dev/sdc, /dev/nvme0n2p1 on /dev/nvme0n2)
        if device is None or disk is None or not device.startswith(disk):
            return False
        suffix = device[len(disk):]
        if suffix == '':
            return True
        if disk[-1].isdigit():
            return re.match(r'^p\d+$', suffix) is not None
        return suffix.isdigit()

    def get_vg_lv_name(self, device):
        '''
            Returns (volume group, logical volume) of an LVM logical volume device, else (None, None).
            /dev/mapper/<vg>-<lv> (a '-' inside a vg or lv name is escaped as '--') or /dev/<vg>/<lv>
        '''
        if device is None:
            return None, None
        if device.startswith('/dev/mapper/'):
            name = device[len('/dev/mapper/'):]
            index = 0
            while index < len(name):
                if name[index] == '-':
                    if index + 1 < len(name) and name[index + 1] == '-':
                        index += 2
                        continue
                    return name[:index].replace('--', '-'), name[index + 1:].replace('--', '-')
                index += 1
            return None, None
        parts = device.split('/')
        if len(parts) == 4 and parts[1] == 'dev' and parts[2] in self.pvs_dict:
            return parts[2], parts[3]
        return None, None

    def get_vg_name(self, device):
        return self.get_vg_lv_name(device)[0]

    def has_azure_os_disk_symlink(self):
        for name in ('root', 'os'):
            if os.path.exists(os.path.join(AZURE_DISK_SYMLINK_DIR, name)):
                return True
        return False

    def get_root_devices(self):
        '''
            Since root devices are at mount points '/', '/boot' and '/boot/efi' we use file_systems_info to find the root_devices based on the mount points.
            Sample output for file_systems_info
            [('sysfs', 'sysfs', '/sys'), ('proc', 'proc', '/proc'), ('udev', 'devtmpfs', '/dev'),..]
            When the root file system is on LVM (/dev/mapper/rootvg-rootlv), the physical volumes of the volume group are added
            so that the OS disk can be identified, unless the Azure udev rules already identify the OS disk.
        '''
        root_devices = []
        for file_system in self.file_systems_info:
            if(file_system[2] in self.os_disk_mount_points and file_system[0] not in root_devices):
                root_devices.append(file_system[0])
        if not self.has_azure_os_disk_symlink():
            for root_device in list(root_devices):
                vg_name = self.get_vg_name(root_device)
                if vg_name is not None and vg_name in self.pvs_dict:
                    for pv in self.pvs_dict[vg_name]:
                        if pv not in root_devices:
                            root_devices.append(pv)
        return root_devices

    def get_disk_luns_from_azure_symlinks(self):
        '''
            Uses the udev symlinks created by WALinuxAgent and azure-vm-utils
              /dev/disk/azure/scsi1/lun<lun>   -> SCSI data disks
              /dev/disk/azure/data/by-lun/<lun> -> NVMe (and SCSI) data disks
              /dev/disk/azure/root, /dev/disk/azure/os -> OS disk
        '''
        disk_luns = {}
        try:
            for link_dir, prefix in ((os.path.join(AZURE_DISK_SYMLINK_DIR, 'scsi1'), 'lun'), (os.path.join(AZURE_DISK_SYMLINK_DIR, 'data', 'by-lun'), '')):
                if not os.path.isdir(link_dir):
                    continue
                for name in os.listdir(link_dir):
                    lun = name[len(prefix):] if name.startswith(prefix) else ''
                    if lun.isdigit(): # skips partition links like lun0-part1
                        disk_luns[os.path.realpath(os.path.join(link_dir, name))] = int(lun)
            for name in ('root', 'os'):
                link = os.path.join(AZURE_DISK_SYMLINK_DIR, name)
                if os.path.exists(link):
                    disk_luns[os.path.realpath(link)] = -1
        except Exception as e:
            errMsg = 'Failed to read the azure disk symlinks with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Warning')
        return disk_luns

    def get_azure_nvme_lun(self, device_name):
        '''
            For Azure remote NVMe disks (model "MSFT NVMe Accelerator v1.0") namespace 1 is the OS disk and namespace N is the data disk at LUN N-2.
            Returns None for other NVMe devices (for example local NVMe temp disks).
        '''
        match = re.match(r'^nvme\d+n(\d+)$', os.path.basename(device_name))
        if match is None:
            return None
        try:
            with open(os.path.join(SYS_BLOCK_DIR, os.path.basename(device_name), 'device', 'model')) as model_file:
                model = model_file.read().strip()
        except (IOError, OSError):
            return None
        if model != AZURE_NVME_REMOTE_DISK_MODEL:
            return None
        namespace_id = int(match.group(1))
        return -1 if namespace_id == 1 else namespace_id - 2

    def add_azure_nvme_disk_luns(self, disk_luns):
        try:
            if not os.path.isdir(SYS_BLOCK_DIR):
                return
            for name in os.listdir(SYS_BLOCK_DIR):
                device_name = '/dev/' + name
                if device_name in disk_luns:
                    continue
                lun = self.get_azure_nvme_lun(device_name)
                if lun is not None:
                    disk_luns[device_name] = lun
        except Exception as e:
            errMsg = 'Failed to enumerate nvme disks with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Warning')

    def is_non_physical_fs(self, fstype):
        fstype = (fstype or '').lower()
        if fstype == 'fuseblk': # FUSE on a local block device, for example ntfs-3g
            return False
        for nonPhysicalFsType in self.non_physical_file_systems:
            if nonPhysicalFsType in fstype:
                return True
        return False

    @staticmethod
    def is_block_device_fs(device, fstype):
        # Only file systems on block devices (and zfs datasets) can be on the backed up disks.
        # This excludes network and cluster file systems whatever their type is called (wekafs, mvfs, cvfs, gpfs, nfs mounted later, ...)
        return device.startswith('/dev/') or (fstype or '').lower() == 'zfs'

    @staticmethod
    def unescape_mount_field(field):
        # /proc/self/mounts escapes space, tab, newline and backslash as octal
        return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), field)

    def get_proc_mounts_fstypes(self):
        '''
            Reads the current mount table so that file systems mounted after the cached mount output was taken also get their type.
            Returns {(device, mount point) : fstype}
        '''
        fstypes = {}
        try:
            if os.path.isfile(PROC_MOUNTS_FILE):
                with open(PROC_MOUNTS_FILE) as mounts_file:
                    for line in mounts_file:
                        fields = line.split()
                        if len(fields) >= 3:
                            fstypes[(self.unescape_mount_field(fields[0]), self.unescape_mount_field(fields[1]))] = fields[2]
        except Exception as e:
            errMsg = 'Failed to read %s with error: %s, stack trace: %s' % (PROC_MOUNTS_FILE, str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Warning')
        return fstypes

    def get_resource_disk_device(self):
        resource_disk_partition = self.resource_disk.get_resource_disk_mount_point(0)
        self.logger.log("resource_disk_device: {0}".format(resource_disk_partition),True)
        if resource_disk_partition:
            return "/dev/{0}".format(resource_disk_partition)
        resource_disk_link = os.path.join(AZURE_DISK_SYMLINK_DIR, 'resource-part1')
        if os.path.exists(resource_disk_link):
            resource_disk_device = os.path.realpath(resource_disk_link)
            self.logger.log("resource_disk_device from {0}: {1}".format(resource_disk_link, resource_disk_device),True)
            return resource_disk_device
        self.logger.log("Unable to detect the resource disk, file systems having {0} at their root will be treated as temporary disks".format(TEMP_DISK_WARNING_FILE),True)
        return None

    def is_temp_disk(self, device, mountpoint, resource_disk_device):
        if resource_disk_device is not None:
            return device == resource_disk_device
        return os.path.isfile(os.path.join(mountpoint, TEMP_DISK_WARNING_FILE))

    def get_df_output(self, command):
        # stdout goes to a file instead of a pipe so that a large df output can't fill the pipe buffer and block df
        df_output_file = tempfile.TemporaryFile()
        try:
            df = subprocess.Popen(command, stdout=df_output_file)
            process_wait_time = DF_TIMEOUT_IN_SECONDS
            while(process_wait_time > 0 and df.poll() is None):
                time.sleep(1)
                process_wait_time -= 1
            self.logger.log("df command executed for process wait time value" + str(process_wait_time), True)
            if df.poll() is None:
                self.logger.log("df command did not complete in {0} seconds".format(DF_TIMEOUT_IN_SECONDS), True, 'Error')
                # not waiting for df to exit, it can be stuck in uninterruptible sleep on a hung network mount
                try:
                    df.kill()
                except Exception:
                    pass
                return None
            self.logger.log("df return code "+str(df.returncode), True)
            df_output_file.seek(0)
            output = df_output_file.read()
        finally:
            df_output_file.close()
        if sys.version_info > (3,):
            return output.decode('utf-8', 'backslashreplace')
        return str(output)

    def get_loop_devices(self):
        global disk_util
        disk_util = DiskUtil.get_instance(patching = self.patching,logger = self.logger)
        if len(self.file_systems_info) == 0 :
            self.file_systems_info = disk_util.get_mount_file_systems()
        self.logger.log("file_systems list : ",True)
        self.logger.log(str(self.file_systems_info),True)
        disk_loop_devices_file_systems = []
        for file_system_info in self.file_systems_info:
            if 'loop' in file_system_info[0]:
                disk_loop_devices_file_systems.append(file_system_info[0])
        return disk_loop_devices_file_systems
  
    def get_disk_luns(self):
        '''
            Returns {disk device : LUN}, the OS disk has the LUN -1.
            Azure udev symlinks are preferred, lsscsi is used for the SCSI disks which are not covered by them and
            sysfs is used for the Azure remote NVMe disks.
            Sample output of the lsscsi command
            [1:0:0:15]   disk    Msft     Virtual Disk     1.0   /dev/sda
            [1:0:0:18]   disk    Msft     Virtual Disk     1.0   /dev/sdc
            [N:0:1:2]    disk    MSFT NVMe Accelerator v1.0__1   /dev/nvme0n2
        '''
        disk_luns = self.get_disk_luns_from_azure_symlinks()
        self.logger.log("LUNs from azure disk symlinks {0}".format(disk_luns))
        for item in self.lsscsi_list:
            try:
                hctl = item[item.index('[') + 1:item.index(']')]
                device_name = item.split()[-1]
                # nvme namespace ids are not LUNs, they are handled by add_azure_nvme_disk_luns
                if hctl.startswith('N:') or not device_name.startswith('/dev/') or device_name in disk_luns:
                    continue
                disk_luns[device_name] = int(hctl.split(':')[-1])
            except Exception as e:
                self.logger.log("Unable to parse the lsscsi line {0}, error {1}".format(item, str(e)), True, 'Warning')
        self.add_azure_nvme_disk_luns(disk_luns)
        for device_name in disk_luns:
            for root_device in self.root_devices:
                if self.is_device_on_disk(root_device, device_name):
                    disk_luns[device_name] = -1 # Changing the Lun# of OS Disk to -1
        return disk_luns

    def disk_list_for_billing(self):
        disk_luns = self.get_disk_luns()
        if(len(disk_luns) != 0):
            for device_name in sorted(disk_luns.keys()):
                lunNumber = disk_luns[device_name]
                if lunNumber in self.includedLunList :
                    self.disksToBeIncluded.append(device_name)
                self.logger.log("LUN Number {0}, disk {1}".format(lunNumber,device_name))
            self.logger.log("Disks to be included {0}".format(self.disksToBeIncluded))
        else:
            self.size_calc_failed = True
            self.logger.log("Unable to map the disks to LUNs using lsscsi, azure disk symlinks or nvme namespaces and therefore size calculation is marked as failed.")

    def is_pv_included(self, pv):
        return any(self.is_device_on_disk(pv, disk) for disk in self.disksToBeIncluded)

    def get_logicalVolumes_for_billing(self):
        partial_vgs = []
        for lvg in self.pvs_dict.keys():
            included_pvs = [pv for pv in self.pvs_dict[lvg] if self.is_pv_included(pv)]
            if len(included_pvs) == len(self.pvs_dict[lvg]):
                self.logicalVolume_to_bill.append(lvg)
            elif len(included_pvs) > 0:
                partial_vgs.append(lvg)
                self.logger.log("The logical volume group {0} spans included and excluded disks, its logical volumes are billed in proportion to their extents on the included disks".format(lvg))
            else:
                self.logger.log("The logical volume group {0} is not on any of the disks to be included".format(lvg))
        self.partial_logicalVolumeGroups = partial_vgs
        if len(partial_vgs) > 0:
            self.get_lvs_list()
            self.build_lv_segments()
        self.logger.log("the lvm list to bill are {0}, partially included lvm list {1}".format(self.logicalVolume_to_bill, self.partial_logicalVolumeGroups))

    def get_lvs_list(self):
        try:
            command = "lvs -a --segments --noheadings --separator : -o vg_name,lv_name,seg_size_pe,devices,pool_lv"
            if (self.sudo_off == 0):
                command = "sudo " + command
            self.lvs_output = os.popen(command).read().strip().splitlines()
        except Exception as e:
            error_msg = "Failed to execute the command \"%s\" because of error %s , stack trace: %s" % (command, str(e), traceback.format_exc())
            self.logger.log(error_msg, True ,'Error')
            self.lvs_output = []

    def build_lv_segments(self):
        '''
            Builds {(volume group, logical volume) : [(segment size in extents, [devices], pool)]} from
            "lvs -a --segments --noheadings --separator : -o vg_name,lv_name,seg_size_pe,devices,pool_lv"
            Sample output:
              datavg:lvlinear:2559:/dev/sdc1(0):
              datavg:lvstriped:512:/dev/sdc1(2559),/dev/sdd1(0):          (striped segment)
              datavg:lvraid:256:lvraid_rimage_0(0),lvraid_rimage_1(0):    (raid / mirror)
              datavg:[lvraid_rimage_0]:256:/dev/sdc1(3071):               (hidden sub volume)
              datavg:thinlv:1024::pool                                    (thin volume)
              datavg:pool:512:pool_tdata(0):                              (thin pool)
        '''
        self.lv_segments = {}
        for line in self.lvs_output:
            fields = [field.strip() for field in line.strip().split(':')]
            if len(fields) < 5:
                continue
            vg_name, lv_name, seg_size, devices, pool = fields[:5]
            try:
                seg_size = int(seg_size)
            except ValueError:
                continue
            devices = [re.sub(r'\(\d+\)$', '', device.strip()).strip('[]') for device in devices.split(',') if device.strip() != '']
            self.lv_segments.setdefault((vg_name, lv_name.strip('[]')), []).append((seg_size, devices, pool.strip('[]')))
        self.logger.log("The lv segments are {0}".format(str(self.lv_segments)))

    def get_lv_extents_per_pv(self, vg_name, lv_name, visited=None):
        # Resolves the extents of a logical volume to physical volumes, following raid/mirror/cache sub volumes and thin pools
        if visited is None:
            visited = set()
        if (vg_name, lv_name) in visited or (vg_name, lv_name) not in self.lv_segments:
            return {}
        visited.add((vg_name, lv_name))
        extents = {}
        for seg_size, devices, pool in self.lv_segments[(vg_name, lv_name)]:
            sub_volumes = [device for device in devices if not device.startswith('/dev/')]
            if len(devices) == 0 and pool != '':
                sub_volumes = [pool]
            for device in devices:
                if device.startswith('/dev/'):
                    extents[device] = extents.get(device, 0) + float(seg_size) / len(devices)
            for sub_volume in sub_volumes:
                for pv, pv_extents in self.get_lv_extents_per_pv(vg_name, sub_volume, visited).items():
                    extents[pv] = extents.get(pv, 0) + pv_extents
        return extents

    def get_lv_billing_fraction(self, device):
        vg_name, lv_name = self.get_vg_lv_name(device)
        if vg_name is None:
            return 0
        if vg_name in self.logicalVolume_to_bill:
            return 1
        if vg_name not in self.partial_logicalVolumeGroups:
            return 0
        extents = self.get_lv_extents_per_pv(vg_name, lv_name)
        total_extents = sum(extents.values())
        if total_extents <= 0:
            self.logger.log("Unable to find the physical volumes of the logical volume {0}".format(device), True)
            return 0
        included_extents = sum(pv_extents for pv, pv_extents in extents.items() if self.is_pv_included(pv))
        fraction = included_extents / total_extents
        self.logger.log("Logical volume {0} has {1} of {2} extents on the included disks".format(device, included_extents, total_extents), True)
        return fraction

    def get_billable_lv_used(self, device, used):
        return int(used * self.get_lv_billing_fraction(device))

    def count_device_once(self, device, used):
        # A block device shows up once per mount (btrfs subvolumes, bind mounts) with the used size of the whole file system
        if device.startswith('/dev/'):
            if device in self.counted_devices:
                self.logger.log("Device {0} is already counted, skipping its used space in KB : {1}".format(device, used), True)
                return 0
            self.counted_devices.add(device)
        return used

    def device_list_for_billing(self):
        self.logger.log("In device_list_for_billing",True)
        devices_to_bill = [] #list to store device names to be billed
        device_items = disk_util.get_device_items(None)
        for device_item in device_items :
            if str(device_item.name).startswith("sd"):
                devices_to_bill.append("/dev/{0}".format(str(device_item.name)))
            else:
                self.logger.log("Not adding device {0} as it does not start with sd".format(str(device_item.name)))
        self.logger.log("Initial billing items {0}".format(devices_to_bill))
        
        '''
            Sample output for file_systems_info
            [('sysfs', 'sysfs', '/sys'), ('proc', 'proc', '/proc'), ('udev', 'devtmpfs', '/dev'),..]
        '''

        # check if user off the sudo usage in commands
        self.sudo_off = self.hutil.get_intvalue_from_configfile("sudo_off", self.sudo_off)
        self.logger.log("sudo flag is {0}".format(self.sudo_off))

        # The command lsscsi is used for mapping the LUN numbers to the disk_names
        self.get_lsscsi_list() #populates self.lsscsi_list 
        self.get_lsblk_list() #populates self.lsblk_list
        self.get_pvs_list()#populates pvs list
        self.build_pvs_dict()

        self.root_devices = self.get_root_devices()
        self.logger.log("root_devices {0}".format(str(self.root_devices)))
        self.logger.log("lsscsi_list {0}".format(self.lsscsi_list))

        self.disk_list_for_billing() 
        self.get_logicalVolumes_for_billing()
        self.logger.log("lsblk o/p {0}".format(self.output_lsblk))
        self.logger.log("lvm {0}".format(self.logicalVolume_to_bill))
        ''' 
                NAME          MOUNTPOINT
                sda
                sda1          /boot/efi
                sda2          /boot
                sda3
                sda4
                rootvg-tmplv  /tmp
                rootvg-usrlv  /usr
                rootvg-optlv  /opt
                rootvg-homelv /home
                rootvg-varlv  /var
                rootvg-rootlv /
                sdb
                sdb1          /mnt/resource

                sdc
                sdc1          /mnt/sdc1
                sdc2          /mnt/sdc2
                sdc3
                sde
                sde1          /mnt/sde1
                sdf
                sdg
	'''
        if(len(self.output_lsblk) == 0):
            self.size_calc_failed = True
            self.logger.log("There is some glitch in executing the command 'lsblk -n --list --output name,mountpoint' and therefore size calculation is marked as failed.")
        
        for item in self.output_lsblk: 
            item_split = item.strip().split(None, 1) # mount points may contain spaces
            if(len(item_split)==2):
                device = item_split[0]
                mount_point = item_split[1]
            else:
                mount_point = ""
                device = ""
            if device != '' and mount_point != '':
                device = '/dev/' + device
                for disk in self.disksToBeIncluded :
                    if self.is_device_on_disk(device, disk) and device not in self.devicesToInclude:
                        self.devicesToInclude.append(device)
                        self.device_mount_points.append(mount_point)
                        break              
        self.logger.log("devices_to_bill: {0}".format(str(self.devicesToInclude)),True) 
        self.logger.log("The mountpoints of devices to bill: {0}".format(str(self.device_mount_points)), True)
        self.logger.log("exiting device_list_for_billing",True)
        return devices_to_bill

    def get_total_used_size(self):
        try:
            self.size_calc_failed = False

            onlyLocalFilesystems = self.hutil.get_strvalue_from_configfile(CommonVariables.onlyLocalFilesystems, "False") 
            # df command gives the information of all the devices which have mount points
            # -P (POSIX format) keeps every file system on a single line
            if onlyLocalFilesystems in ['True', 'true']:  
                df_command = ["df" , "-klP"]
            else:
                df_command = ["df" , "-kP"]

            '''
            Sample output of the df command
            Filesystem                                              1024-blocks    Used Available Capacity Mounted on
            /dev/sda2                                                  52155392 3487652  48667740       7% /
            devtmpfs                                                    7170976       0   7170976       0% /dev
            tmpfs                                                       7180624       0   7180624       0% /dev/shm
            tmpfs                                                       7180624  760496   6420128      11% /run
            tmpfs                                                       7180624       0   7180624       0% /sys/fs/cgroup
            /dev/sda1                                                    245679  151545     76931      67% /boot
            /dev/sdb1                                                  28767204 2142240  25140628       8% /mnt/resource
            /dev/mapper/mygroup-thinv1                                  1041644   33520   1008124       4% /bricks/brick1
            /dev/mapper/mygroup-85197c258a54493da7880206251f5e37_0      1041644   33520   1008124       4% /run/gluster/snaps/85197c258a54493da7880206251f5e37/brick2
            /dev/mapper/mygroup2-thinv2                                15717376 5276944  10440432      34% /tmp/test
            /dev/mapper/mygroup2-63a858543baf4e40a3480a38a2f232a0_0    15717376 5276944  10440432      34% /run/gluster/snaps/63a858543baf4e40a3480a38a2f232a0/brick2
            tmpfs                                                       1436128       0   1436128       0% /run/user/1000
            //Centos72test/cifs_test                                   52155392 4884620  47270772      10% /mnt/cifs_test2
            '''
            output = self.get_df_output(df_command)
            if output is None:
                self.logger.log("Unable to get the output of df, so marking the size computation as failed and returning zero", True)
                self.size_calc_failed = True
                return 0,self.size_calc_failed
            output = output.strip().splitlines()
            self.logger.log("output of df : {0}".format(str(output)),True)
            disk_loop_devices_file_systems = self.get_loop_devices()
            self.logger.log("outside loop device", True)
            total_used = 0
            total_used_network_shares = 0
            total_used_gluster = 0
            total_used_loop_device=0
            total_used_temporary_disks = 0 
            total_used_ram_disks = 0
            total_used_unknown_fs = 0
            actual_temp_disk_used = 0
            total_sd_size = 0
            network_fs_types = []
            unknown_fs_types = []
            excluded_disks_used = 0
            totalSpaceUsed = 0
            device_list = []
      
            if len(self.file_systems_info) == 0 :
                self.file_systems_info = disk_util.get_mount_file_systems()

            output_length = len(output)
            index = 1
            df_parse_failed = False
            self.counted_devices = set()
            proc_mount_fstypes = self.get_proc_mounts_fstypes()
            self.resource_disk = ResourceDiskUtil(patching = self.patching, logger = self.logger)
            resource_disk_device = self.get_resource_disk_device()
            self.logger.log("ResourceDisk is excluded in billing as it represents the Actual Temporary disk")

            if(self.LunListEmpty != True and self.isAnyDiskExcluded == True):
                device_list = self.device_list_for_billing() #new logic: calculate the disk size for billing

            while index < output_length:
                df_line = DF_LINE_REGEX.match(output[index].rstrip('\r'))
                if df_line is None:
                    if output[index].strip() != '':
                        self.logger.log("Output of df command is not in desired format, skipping the line : {0}".format(output[index]),True)
                        df_parse_failed = True
                    index = index + 1
                    continue
                device = df_line.group('device')
                size = df_line.group('size')
                used = df_line.group('used')
                available = df_line.group('available')
                mountpoint = df_line.group('mountpoint')
                if used == '-':
                    used = '0'
                fstype = ''
                isNetworkFs = False
                isKnownFs = False

                if int(used) < 0 :
                    self.logger.log("The used space is negative, so marking the size computation as failed and returning zero")
                    self.size_calc_failed = True
                    return 0,self.size_calc_failed

                fstype = proc_mount_fstypes.get((device, mountpoint), '')
                if fstype == '':
                    for file_system_info in self.file_systems_info:
                        if device == file_system_info[0] and mountpoint == file_system_info[2]:
                            fstype = file_system_info[1]
                self.logger.log("index :{0} Device name : {1} fstype : {2} size : {3} used space in KB : {4} available space : {5} mountpoint : {6}".format(index,device,fstype,size,used,available,mountpoint),True)

                isNetworkFs = self.is_non_physical_fs(fstype)

                for knownFs in self.known_fs:
                    if knownFs in fstype.lower():
                        isKnownFs = True
                        break

                if device == resource_disk_device and self.isOnlyOSDiskBackupEnabled == False : # adding log to check difference in billing of temp disk
                    self.logger.log("Actual temporary disk, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    actual_temp_disk_used= int(used)
                
                if device in device_list and device != resource_disk_device :
                    self.logger.log("Adding sd* partition, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_sd_size = total_sd_size + int(used) #calcutale total sd* size just skip temp disk

                if not (isKnownFs or fstype == '' or fstype == None):
                    unknown_fs_types.append(fstype)

                if isNetworkFs :
                    if fstype not in network_fs_types :
                        network_fs_types.append(fstype)
                    self.logger.log("Not Adding network-drive, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                elif self.isOnlyOSDiskBackupEnabled == False and self.is_temp_disk(device, mountpoint, resource_disk_device) :
                    self.logger.log("Not Adding temporary disk, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_temporary_disks = total_used_temporary_disks + int(used)

                elif "tmpfs" in fstype.lower() or "devtmpfs" in fstype.lower() or "ramdiskfs" in fstype.lower() or "rootfs" in fstype.lower():
                    self.logger.log("Not Adding RAM disks, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_ram_disks = total_used_ram_disks + int(used)

                elif 'loop' in device and device not in disk_loop_devices_file_systems:
                    self.logger.log("Not Adding Loop Device , Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_loop_device = total_used_loop_device + int(used)

                elif (mountpoint.startswith('/run/gluster/snaps/')):
                    self.logger.log("Not Adding Gluster Device , Device name : {0} used space in KB : {1} mount point : {2}".format(device,used,mountpoint),True)
                    total_used_gluster = total_used_gluster + int(used)

                elif device.startswith( '\\\\' ) or device.startswith( '//' ):
                    self.logger.log("Not Adding network-drive as it starts with slahes, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                elif not self.is_block_device_fs(device, fstype):
                    if fstype not in network_fs_types :
                        network_fs_types.append(fstype)
                    self.logger.log("Not Adding as it is not on a block device, Device name : {0} used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                else:
                    #Only when OS disk is included
                    if(self.isOnlyOSDiskBackupEnabled == True):
                        if(mountpoint == '/'):
                            total_used = total_used + self.count_device_once(device, int(used))
                            self.logger.log("Adding only root device to size calculation. Device name : {0} used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            self.logger.log("Total Used Space: {0}".format(total_used),True)
                    #Handling a case where LunList is empty for UnmanagedVM's and failures if occurred( as we will billing for all the non resource disks)
                    elif( (self.size_calc_failed == True or self.LunListEmpty == True) and device != resource_disk_device):
                        self.logger.log("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                        total_used = total_used + self.count_device_once(device, int(used)) #return in KB
                    #LunList is empty but the device is an actual temporary disk so excluding it
                    elif( (self.size_calc_failed == True or self.LunListEmpty == True) and device == resource_disk_device):
                        self.logger.log("Device {0} is not included for billing as it is a resource disk, used space in KB : {1} mount point : {2} fstype :{3}".format(device,used,mountpoint,fstype),True)
                        excluded_disks_used = excluded_disks_used + int(used)
                    #Including only the disks which are asked to include (Here LunList can't be empty this case is handled at the CRP end)
                    else:
                        if self.isAnyDiskExcluded == False and device != resource_disk_device:
                            #No disk has been excluded So can include every non resource disk
                            self.logger.log("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            total_used = total_used + self.count_device_once(device, int(used)) #return in KB
                        elif self.isAnyDiskExcluded == False and device == resource_disk_device:
                            #excluding resource disk even in the case where all disks are included as it is the actual temporary disk
                            self.logger.log("Device {0} is not included for billing as it is a resource disk, used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            excluded_disks_used = excluded_disks_used + int(used)
                        elif mountpoint in self.device_mount_points and device != resource_disk_device:
                            self.logger.log("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            total_used = total_used + self.count_device_once(device, int(used)) #return in KB
                        elif device != resource_disk_device and -1 in self.includedLunList:
                            if mountpoint in self.root_mount_points :
                                self.logger.log("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                total_used = total_used + self.count_device_once(device, int(used)) #return in KB
                            else:
                                #check for logicalVolumes
                                billable_lv_used = self.get_billable_lv_used(device, int(used))
                                if(billable_lv_used > 0):
                                    self.logger.log("Adding Device name : {0} for billing used space in KB : {1} billed used space in KB : {2} mount point : {3} fstype : {4}".format(device,used,billable_lv_used,mountpoint,fstype),True)
                                    total_used = total_used + self.count_device_once(device, billable_lv_used) #return in KB
                                    excluded_disks_used = excluded_disks_used + int(used) - billable_lv_used
                                else:
                                    self.logger.log("Device {0} is not included for billing as it is not part of the disks to be included, used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                    excluded_disks_used = excluded_disks_used + int(used)
                        else:
                            # check for logicalVolumes even if os disk is not included
                            billable_lv_used = self.get_billable_lv_used(device, int(used))
                            if(billable_lv_used > 0):
                                self.logger.log("Adding Device name : {0} for billing used space in KB : {1} billed used space in KB : {2} mount point : {3} fstype : {4}".format(device,used,billable_lv_used,mountpoint,fstype),True)
                                total_used = total_used + self.count_device_once(device, billable_lv_used) #return in KB
                                excluded_disks_used = excluded_disks_used + int(used) - billable_lv_used
                            else:
                                self.logger.log("Device {0} is not included for billing as it is not part of the disks to be included, used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                excluded_disks_used = excluded_disks_used + int(used)
                    if not (isKnownFs or fstype == '' or fstype == None):
                        total_used_unknown_fs = total_used_unknown_fs + int(used)

                index = index + 1

            if not len(unknown_fs_types) == 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("unknownFSTypeInDf",str(unknown_fs_types))
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalUsedunknownFS",str(total_used_unknown_fs))
                self.logger.log("Total used space in Bytes of unknown FSTypes : {0}".format(total_used_unknown_fs * 1024),True)

            if total_used_temporary_disks != actual_temp_disk_used :
                self.logger.log("Billing differenct because of incorrect temp disk: {0}".format(str(total_used_temporary_disks - actual_temp_disk_used)))

            if not len(network_fs_types) == 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("networkFSTypeInDf",str(network_fs_types))
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalUsedNetworkShare",str(total_used_network_shares))
                self.logger.log("Total used space in Bytes of network shares : {0}".format(total_used_network_shares * 1024),True)
            if total_used_gluster !=0 :
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("glusterFSSize",str(total_used_gluster))
            if total_used_temporary_disks !=0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("tempDisksSize",str(total_used_temporary_disks))
            if total_used_ram_disks != 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("ramDisksSize",str(total_used_ram_disks))
            if total_used_loop_device != 0 :
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("loopDevicesSize",str(total_used_loop_device))
            totalSpaceUsed = total_used + excluded_disks_used
            self.logger.log("TotalUsedSpace ( both included and excluded disks ) in Bytes : {0} , TotalUsedSpaceAfterExcludeLUN in Bytes : {1} , TotalLUNExcludedUsedSpace in Bytes : {2} ".format(totalSpaceUsed *1024 , total_used * 1024 , excluded_disks_used *1024 ),True)
            if total_sd_size != 0 :
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalsdSize",str(total_sd_size))
            self.logger.log("Total sd* used space in Bytes : {0}".format(total_sd_size * 1024),True)
            if df_parse_failed:
                self.size_calc_failed = True
            self.logger.log("SizeComputationFailedFlag {0}".format(self.size_calc_failed))
            return total_used * 1024,self.size_calc_failed #Converting into Bytes
        except Exception as e:
            errMsg = 'Unable to fetch total used space with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg,True)
            self.size_calc_failed = True
            return 0,self.size_calc_failed
