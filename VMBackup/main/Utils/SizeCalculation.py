import os
import os.path
import sys
try:
    import imp as imp
except ImportError:
    import importlib as imp
import base64
import json
import tempfile
import time
from Utils.DiskUtil import DiskUtil
import Utils.HandlerUtil
import traceback
import subprocess

class SizeCalculation(object):

    def __init__(self,patching,logger,para_parser):
        self.patching=patching
        self.logger=logger
        self.file_systems_info = []
        self.non_physical_file_systems = ['fuse', 'nfs', 'cifs', 'overlay', 'aufs', 'lustre', 'secfs2', 'zfs', 'btrfs', 'iso']
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

    def get_loop_devices(self):
        global disk_util
        disk_util = DiskUtil(patching = self.patching,logger = self.logger)
        if len(self.file_systems_info) == 0 :
            self.file_systems_info = disk_util.get_mount_file_systems()
        self.logger.log("file_systems list : ",True)
        self.logger.log(str(self.file_systems_info),True)
        disk_loop_devices_file_systems = []
        for file_system_info in self.file_systems_info:
            if 'loop' in file_system_info[0]:
                disk_loop_devices_file_systems.append(file_system_info[0])
        return disk_loop_devices_file_systems

    def get_total_used_size(self):
        try:
            size_calc_failed = False
            df = subprocess.Popen(["df" , "-k"], stdout=subprocess.PIPE)
            '''
            Sample output of the df command

            Filesystem                                              Type     1K-blocks    Used    Avail Use% Mounted on
            /dev/sda2                                               xfs       52155392 3487652 48667740   7% /
            devtmpfs                                                devtmpfs   7170976       0  7170976   0% /dev
            tmpfs                                                   tmpfs      7180624       0  7180624   0% /dev/shm
            tmpfs                                                   tmpfs      7180624  760496  6420128  11% /run
            tmpfs                                                   tmpfs      7180624       0  7180624   0% /sys/fs/cgroup
            /dev/sda1                                               ext4        245679  151545    76931  67% /boot
            /dev/sdb1                                               ext4      28767204 2142240 25140628   8% /mnt/resource
            /dev/mapper/mygroup-thinv1                              xfs        1041644   33520  1008124   4% /bricks/brick1
            /dev/mapper/mygroup-85197c258a54493da7880206251f5e37_0  xfs        1041644   33520  1008124   4% /run/gluster/snaps/85197c258a54493da7880206251f5e37/brick2
            /dev/mapper/mygroup2-thinv2                             xfs       15717376 5276944 10440432  34% /tmp/test
            /dev/mapper/mygroup2-63a858543baf4e40a3480a38a2f232a0_0 xfs       15717376 5276944 10440432  34% /run/gluster/snaps/63a858543baf4e40a3480a38a2f232a0/brick2
            tmpfs                                                   tmpfs      1436128       0  1436128   0% /run/user/1000
            //Centos72test/cifs_test                                cifs      52155392 4884620 47270772  10% /mnt/cifs_test2

            '''
            output = ""
            process_wait_time = 300
            while(df is not None and process_wait_time >0 and df.poll() is None):
                time.sleep(1)
                process_wait_time -= 1
            self.logger.log("df command executed for process wait time value" + str(process_wait_time), True)
            if(df is not None and df.poll() is not None):
                self.logger.log("df return code"+str(df.returncode), True)
                output = df.stdout.read()
            if sys.version_info > (3,):
                output = str(output, encoding='utf-8', errors="backslashreplace")
            else:
                output = str(output)
            output = output.strip().split("\n")
            disk_loop_devices_file_systems = self.get_loop_devices()
            self.logger.log("outside loop device", True)
            total_used = 0
            total_used_network_shares = 0
            total_used_gluster = 0
            total_used_loop_device=0
            total_used_temporary_disks = 0 
            total_used_ram_disks = 0
            total_used_unknown_fs = 0
            network_fs_types = []
            unknown_fs_types = []
      
            if len(self.file_systems_info) == 0 :
                self.file_systems_info = disk_util.get_mount_file_systems()

            output_length = len(output)
            index = 1
            while index < output_length:
                if(len(output[index].split()) < 6 ): #when a row is divided in 2 lines
                    index = index+1
                    if(index < output_length and len(output[index-1].split()) + len(output[index].split()) == 6):
                        output[index] = output[index-1] + output[index]
                    else:
                        self.logger.log("Output of df command is not in desired format",True)
                        total_used = 0
                        size_calc_failed = True
                        break
                device, size, used, available, percent, mountpoint = output[index].split()
                fstype = ''
                isNetworkFs = False
                isKnownFs = False


                for file_system_info in self.file_systems_info:
                    if device == file_system_info[0] and mountpoint == file_system_info[2]:
                        fstype = file_system_info[1]
                self.logger.log("Device name : {0} fstype : {1} size : {2} used space in KB : {3} available space : {4} mountpoint : {5}".format(device,fstype,size,used,available,mountpoint),True)

                for nonPhysicaFsType in self.non_physical_file_systems:
                    if nonPhysicaFsType in fstype.lower():
                        isNetworkFs = True
                        break

                for knownFs in self.known_fs:
                    if knownFs in fstype.lower():
                        isKnownFs = True
                        break

                if not (isKnownFs or fstype == '' or fstype == None):
                    unknown_fs_types.append(fstype)

                if isNetworkFs :
                    if fstype not in network_fs_types :
                        network_fs_types.append(fstype)
                    self.logger.log("Not Adding network-drive, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                elif device == '/dev/sdb1' and self.isOnlyOSDiskBackupEnabled == False : #<todo> in some cases root is mounted on /dev/sdb1
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

                else:
                    if(self.isOnlyOSDiskBackupEnabled == True):
                        if(mountpoint == '/'):
                            total_used = total_used + int(used)
                            self.logger.log("Adding only root device to size calculation. Device name : {0} used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            self.logger.log("Total Used Space: {0}".format(total_used),True)
                    else:
                        self.logger.log("Adding Device name : {0} used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                        total_used = total_used + int(used) #return in KB
                    if not (isKnownFs or fstype == '' or fstype == None):
                        total_used_unknown_fs = total_used_unknown_fs + int(used)

                index = index + 1

            if not len(unknown_fs_types) == 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("unknownFSTypeInDf",str(unknown_fs_types))
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalUsedunknownFS",str(total_used_unknown_fs))
                self.logger.log("Total used space in Bytes of unknown FSTypes : {0}".format(total_used_unknown_fs * 1024),True)

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
            self.logger.log("Total used space in Bytes : {0}".format(total_used * 1024),True)
            return total_used * 1024, size_calc_failed #Converting into Bytes
        except Exception as e:
            errMsg = 'Unable to fetch total used space with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg,True)
            size_calc_failed = True
            return 0,size_calc_failed


