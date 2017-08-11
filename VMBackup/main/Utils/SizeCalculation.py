import os
import os.path
import sys
import imp
import base64
import json
import tempfile
import time
from DiskUtil import DiskUtil
import HandlerUtil
import traceback
import subprocess

class SizeCalculation(object):

    def __init__(self,patching,logger):
        self.patching=patching
        self.logger=logger
        self.file_systems_info = []
        

    def get_loop_devices(self):
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
        
            process_wait_time = 30
            while(process_wait_time >0 and df.poll() is None):
                time.sleep(1)
                process_wait_time -= 1

            disk_loop_devices_file_systems = self.get_loop_devices()
            output = df.stdout.read()
            output = output.strip().split("\n")
            total_used = 0
            total_used_network_shares = 0
            total_used_gluster = 0
            total_used_loop_device=0
            total_used_temporary_disks = 0 
            total_used_ram_disks = 0 
            network_fs_types = []
      
            if len(self.file_systems_info) == 0 :
                self.file_systems_info = disk_util.get_mount_file_systems()

            for line in output[1:]:
                device, size, used, available, percent, mountpoint = line.split()
                fstype = ''
                for file_system_info in self.file_systems_info:
                    if device == file_system_info[0] and mountpoint == file_system_info[2]:
                        fstype = file_system_info[1]
                self.logger.log("Device name : {0} fstype : {1} size : {2} used space in KB : {3} available space : {4} mountpoint : {5}".format(device,fstype,size,used,available,mountpoint),True)
                if device == '/dev/sdb1' :
                    self.logger.log("Not Adding temporary disk, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_temporary_disks = total_used_temporary_disks + int(used) 

                elif "fuse" in fstype.lower() or "nfs" in fstype.lower() or "cifs" in fstype.lower():
                    if fstype not in network_fs_types :
                        network_fs_types.append(fstype)
                    self.logger.log("Not Adding network-drive, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                elif "tmpfs" in fstype.lower() or "devtmpfs" in fstype.lower() or "ramdiskfs" in fstype.lower():
                    self.logger.log("Not Adding RAM disks, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_ram_disks = total_used_ram_disks + int(used)

                elif 'loop' in device and device not in disk_loop_devices_file_systems:
                    self.logger.log("Not Adding Loop Device , Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_loop_device = total_used_loop_device + int(used)

                elif (mountpoint.startswith('/run/gluster/snaps/')):
                    self.logger.log("Not Adding Gluster Device , Device name : {0} used space in KB : {1} mount point : {2}".format(device,used,mountpoint),True)
                    total_used_gluster = total_used_gluster + int(used)   

                else:
                    self.logger.log("Adding Device name : {0} used space in KB : {1} mount point : {2}".format(device,used,mountpoint),True)
                    total_used = total_used + int(used) #return in KB

            if not len(network_fs_types) == 0:
                HandlerUtil.HandlerUtility.add_to_telemetery_data("networkFSTypeInDf",str(network_fs_types))
                HandlerUtil.HandlerUtility.add_to_telemetery_data("totalUsedNetworkShare",str(total_used_network_shares))
                self.logger.log("Total used space in Bytes of network shares : {0}".format(total_used_network_shares * 1024),True)
            if total_used_gluster !=0 :
                HandlerUtil.HandlerUtility.add_to_telemetery_data("glusterFSSize",str(total_used_gluster))
            if total_used_temporary_disks !=0:
                HandlerUtil.HandlerUtility.add_to_telemetery_data("tempDisksSize",str(total_used_temporary_disks))
            if total_used_ram_disks != 0:
                HandlerUtil.HandlerUtility.add_to_telemetery_data("ramDisksSize",str(total_used_ram_disks))
            if total_used_loop_device != 0 :
                HandlerUtil.HandlerUtility.add_to_telemetery_data("loopDevicesSize",str(total_used_loop_device))
            self.logger.log("Total used space in Bytes : {0}".format(total_used * 1024),True)
            return total_used * 1024,False #Converting into Bytes
        except Exception as e:
            errMsg = 'Unable to fetch total used space with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg,True)
            return 0,True


