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
import tempfile
import time
from Utils.DiskUtil import DiskUtil
from Utils.ResourceDiskUtil import ResourceDiskUtil
import Utils.HandlerUtil
import traceback
import subprocess
import shlex
from common import CommonVariables

class SizeCalculation(object):

    def __init__(self,patching, hutil, logger,):
        self.patching = patching
        self.logger = logger
        self.hutil = hutil
        self.includedLunList = []
        self.file_systems_info = []
        self.non_physical_file_systems = ['fuse', 'nfs', 'cifs', 'overlay', 'aufs', 'lustre', 'secfs2', 'zfs', 'btrfs', 'iso']
        self.known_fs = ['ext3', 'ext4', 'jfs', 'xfs', 'reiserfs', 'devtmpfs', 'tmpfs', 'rootfs', 'fuse', 'nfs', 'cifs', 'overlay', 'aufs', 'lustre', 'secfs2', 'zfs', 'btrfs', 'iso']
        self.isOnlyOSDiskBackupEnabled = False

        self.disksToBeIncluded = []
        self.root_devices = []
        self.root_mount_points = ['/' , '/boot/efi']

        self.devicesToInclude = [] #partitions to be included
        self.device_mount_points = []
        self.isAnyDiskExcluded = False
        self.LunListEmpty = False
        self.logicalVolume_to_bill = []
        self.sudo_off = 0 # run the commands using sudo
        self.isAnyDiskExcluded = True
        self.includedLunList = [0]
        print(self.includedLunList)
        if(self.includedLunList == None or len(self.includedLunList) == 0):
            self.LunListEmpty = True
            print("As the LunList is empty including all disks")
        print("calling used size")

    
    def get_lsscsi_list(self):
        command = "lsscsi"
        if (self.sudo_off == 0):
            command = "sudo " + command
        try:
            print("executing command  {0}".format(command))
            self.lsscsi_list = (os.popen(command).read()).splitlines()
        except Exception as e:
            error_msg = "Failed to execute the command \"%s\" because of error %s , stack trace: %s" % (command, str(e), traceback.format_exc())
            print(error_msg, 'Error')
            self.lsscsi_list = []

    def get_lsblk_list(self):
        try:
            self.output_lsblk = os.popen("lsblk -n --list --output name,mountpoint").read().strip().splitlines()
        except Exception as e:
            error_msg = "Failed to execute the command lsblk -n --list --output name,mountpoint because of error %s , stack trace: %s" % (str(e), traceback.format_exc())
            print(error_msg, 'Error')
            self.output_lsblk = []

    def get_pvs_list(self):
        try:
            command = "pvs"
            if (self.sudo_off == 0):
                command = "sudo " + command
            self.pvs_output = os.popen(command).read().strip().split("\n")
            self.pvs_output = self.pvs_output[1:]
        except Exception as e:
            error_msg = "Failed to execute the command \"%s\" because of error %s , stack trace: %s" % (command, str(e), traceback.format_exc())
            print(error_msg,'Error')
            self.pvs_output = []

    def get_loop_devices(self):
        global disk_util
        disk_util = DiskUtil.get_instance(patching = self.patching,logger = self.logger)
        if len(self.file_systems_info) == 0 :
            self.file_systems_info = disk_util.get_mount_file_systems()
        print("file_systems list : ",True)
        print(str(self.file_systems_info),True)
        disk_loop_devices_file_systems = []
        for file_system_info in self.file_systems_info:
            if 'loop' in file_system_info[0]:
                disk_loop_devices_file_systems.append(file_system_info[0])
        return disk_loop_devices_file_systems
  
    def disk_list_for_billing(self):
        if(len(self.lsscsi_list) != 0):
            for item in self.lsscsi_list:
                idxOfColon = item.rindex(':',0,item.index(']'))# to get the index of last ':'
                idxOfColon += 1
                lunNumber = int(item[idxOfColon:item.index(']')])
                # item_split is the list of elements present in the one row of the cmd sudo lsscsi
                self.item_split = item.split()
                #storing the corresponding device name from the list
                device_name = self.item_split[len(self.item_split)-1]

                for device in self.root_devices :
                    if device_name in device :
                        lunNumber = -1
                        # Changing the Lun# of OS Disk to -1

                if lunNumber in self.includedLunList :
                    self.disksToBeIncluded.append(device_name)
                print("LUN Number {0}, disk {1}".format(lunNumber,device_name))   
            print("Disks to be included {0}".format(self.disksToBeIncluded))
        else:
            self.size_calc_failed = True
            print("There is some glitch in executing the command 'lsscsi' and therefore size calculation is marked as failed.")

    def get_logicalVolumes_for_billing(self):
        try:
            self.pvs_dict = {}
            for pvs_item in self.pvs_output:
                pvs_item_split  = pvs_item.strip().split()
                if(len(pvs_item_split) > 2):
                    physicalVolume = pvs_item_split[0]
                    logicalVolumeGroup = pvs_item_split[1]
                    if(logicalVolumeGroup in self.pvs_dict.keys()):
                        self.pvs_dict.get(logicalVolumeGroup).append(physicalVolume)
                    else:
                        self.pvs_dict[logicalVolumeGroup] = []
                        self.pvs_dict.get(logicalVolumeGroup).append(physicalVolume)
            print("The pvs_dict contains {0}".format(str(self.pvs_dict)))
        except Exception as e:
            errMsg = 'Failed to serialize pvs_output with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            print(errMsg, True, 'Error') 
        for lvg in self.pvs_dict.keys():
            count = 0
            for disk in self.disksToBeIncluded:
                for pv in self.pvs_dict[lvg]:
                    if(disk in pv):
                        count = count+1
            if(count == len(self.pvs_dict[lvg])):
                lvg = "/dev/mapper/" + lvg
                self.logicalVolume_to_bill.append(lvg)
            else:
                print("Partial snapshotting for the logical volume group {0} can't be taken".format(lvg))
        print("the lvm list to bill are {0}".format(self.logicalVolume_to_bill))

    def device_list_for_billing(self):
        print("In device_list_for_billing",True)
        devices_to_bill = [] #list to store device names to be billed
        device_items = disk_util.get_device_items(None)
        for device_item in device_items :
            if str(device_item.name).startswith("sd"):
                devices_to_bill.append("/dev/{0}".format(str(device_item.name)))
            else:
                print("Not adding device {0} as it does not start with sd".format(str(device_item.name)))
        print("Initial billing items {0}".format(devices_to_bill))
        
        '''
            Sample output for file_systems_info
            [('sysfs', 'sysfs', '/sys'), ('proc', 'proc', '/proc'), ('udev', 'devtmpfs', '/dev'),..]
            Since root devices are at mount points '/' and '/boot/efi' we use file_system_info to find the root_devices based on the mount points.
        '''

        # check if user off the sudo usage in commands
        self.sudo_off = self.hutil.get_intvalue_from_configfile("sudo_off", self.sudo_off)
        print("sudo flag is {0}".format(self.sudo_off))

        # The command lsscsi is used for mapping the LUN numbers to the disk_names
        self.get_lsscsi_list() #populates self.lsscsi_list 
        self.get_lsblk_list() #populates self.lsblk_list
        self.get_pvs_list()#populates pvs list

        for file_system in self.file_systems_info:
            if(file_system[2] in self.root_mount_points):
                self.root_devices.append(file_system[0])
        print("root_devices {0}".format(str(self.root_devices)))
        print("lsscsi_list {0}".format(self.lsscsi_list))
        '''
            Sample output of the lsscsi command 
            [1:0:0:15]   disk    Msft     Virtual Disk     1.0   /dev/sda
            [1:0:0:18]   disk    Msft     Virtual Disk     1.0   /dev/sdc
        '''

        self.disk_list_for_billing() 
        self.get_logicalVolumes_for_billing()
        print("lsblk o/p {0}".format(self.output_lsblk))
        print("lvm {0}".format(self.logicalVolume_to_bill))
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
            print("There is some glitch in executing the command 'lsblk -n --list --output name,mountpoint' and therefore size calculation is marked as failed.")
        
        for item in self.output_lsblk: 
            item_split = item.split()
            if(len(item_split)==2):
                device = item_split[0]
                mount_point = item_split[1]
            else:
                mount_point = ""
                device = ""
            if device != '' and mount_point != '':
                device = '/dev/' + device
                for disk in self.disksToBeIncluded :
                    if disk in device and device not in self.devicesToInclude:
                        self.devicesToInclude.append(device)
                        self.device_mount_points.append(mount_point)
                        break              
        print("devices_to_bill: {0}".format(str(self.devicesToInclude)),True) 
        print("The mountpoints of devices to bill: {0}".format(str(self.device_mount_points)), True)
        print("exiting device_list_for_billing",True)
        return devices_to_bill

    def get_total_used_size(self):
        try:
            self.size_calc_failed = False

            onlyLocalFilesystems = self.hutil.get_strvalue_from_configfile(CommonVariables.onlyLocalFilesystems, "False") 
            # df command gives the information of all the devices which have mount points
            if onlyLocalFilesystems in ['True', 'true']:  
                df = subprocess.Popen(["df" , "-kl"], stdout=subprocess.PIPE)
            else:
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
            print("df command executed for process wait time value" + str(process_wait_time), True)
            if(df is not None and df.poll() is not None):
                print("df return code "+str(df.returncode), True)
                output = df.stdout.read().decode()
            if sys.version_info > (3,):
                try:
                    output = str(output, encoding='utf-8', errors="backslashreplace")
                except:
                    output = str(output)
            else:
                output = str(output)
            output = output.strip().split("\n")
            print("output of df : {0}".format(str(output)),True)
            disk_loop_devices_file_systems = self.get_loop_devices()
            print("outside loop device", True)
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
            self.resource_disk = ResourceDiskUtil(patching = self.patching, logger = self.logger)
            resource_disk_device = self.resource_disk.get_resource_disk_mount_point(0)
            print("resource_disk_device: {0}".format(resource_disk_device),True)
            resource_disk_device = "/dev/{0}".format(resource_disk_device)
            print("ResourceDisk is excluded in billing as it represents the Actual Temporary disk")

            if(self.LunListEmpty != True and self.isAnyDiskExcluded == True):
                device_list = self.device_list_for_billing() #new logic: calculate the disk size for billing

            while index < output_length:
                if(len(Utils.HandlerUtil.HandlerUtility.split(self.logger, output[index])) < 6 ): #when a row is divided in 2 lines
                    index = index+1
                    if(index < output_length and len(Utils.HandlerUtil.HandlerUtility.split(self.logger, output[index-1])) + len(Utils.HandlerUtil.HandlerUtility.split(self.logger, output[index])) == 6):
                        output[index] = output[index-1] + output[index]
                    else:
                        print("Output of df command is not in desired format",True)
                        total_used = 0
                        self.size_calc_failed = True
                        break
                device, size, used, available, percent, mountpoint =Utils.HandlerUtil.HandlerUtility.split(self.logger, output[index])
                fstype = ''
                isNetworkFs = False
                isKnownFs = False

                if int(used) < 0 :
                    print("The used space is negative, so marking the size computation as failed and returning zero")
                    self.size_calc_failed = True
                    return 0,self.size_calc_failed

                for file_system_info in self.file_systems_info:
                    if device == file_system_info[0] and mountpoint == file_system_info[2]:
                        fstype = file_system_info[1]
                print("index :{0} Device name : {1} fstype : {2} size : {3} used space in KB : {4} available space : {5} mountpoint : {6}".format(index,device,fstype,size,used,available,mountpoint),True)

                for nonPhysicaFsType in self.non_physical_file_systems:
                    if nonPhysicaFsType in fstype.lower():
                        isNetworkFs = True
                        break

                for knownFs in self.known_fs:
                    if knownFs in fstype.lower():
                        isKnownFs = True
                        break

                if device == resource_disk_device and self.isOnlyOSDiskBackupEnabled == False : # adding log to check difference in billing of temp disk
                    print("Actual temporary disk, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    actual_temp_disk_used= int(used)
                
                if device in device_list and device != resource_disk_device :
                    print("Adding sd* partition, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_sd_size = total_sd_size + int(used) #calcutale total sd* size just skip temp disk

                if not (isKnownFs or fstype == '' or fstype == None):
                    unknown_fs_types.append(fstype)

                if isNetworkFs :
                    if fstype not in network_fs_types :
                        network_fs_types.append(fstype)
                    print("Not Adding network-drive, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                elif device == "/dev/sdb1"  and self.isOnlyOSDiskBackupEnabled == False : #<todo> in some cases root is mounted on /dev/sdb1
                    print("Not Adding temporary disk, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_temporary_disks = total_used_temporary_disks + int(used)

                elif "tmpfs" in fstype.lower() or "devtmpfs" in fstype.lower() or "ramdiskfs" in fstype.lower() or "rootfs" in fstype.lower():
                    print("Not Adding RAM disks, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_ram_disks = total_used_ram_disks + int(used)

                elif 'loop' in device and device not in disk_loop_devices_file_systems:
                    print("Not Adding Loop Device , Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_loop_device = total_used_loop_device + int(used)

                elif (mountpoint.startswith('/run/gluster/snaps/')):
                    print("Not Adding Gluster Device , Device name : {0} used space in KB : {1} mount point : {2}".format(device,used,mountpoint),True)
                    total_used_gluster = total_used_gluster + int(used)

                elif device.startswith( '\\\\' ) or device.startswith( '//' ):
                    print("Not Adding network-drive as it starts with slahes, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype),True)
                    total_used_network_shares = total_used_network_shares + int(used)

                else:
                    #Only when OS disk is included
                    if(self.isOnlyOSDiskBackupEnabled == True):
                        if(mountpoint == '/'):
                            total_used = total_used + int(used)
                            print("Adding only root device to size calculation. Device name : {0} used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            print("Total Used Space: {0}".format(total_used),True)
                    #Handling a case where LunList is empty for UnmanagedVM's and failures if occurred( as we will billing for all the non resource disks)
                    elif( (self.size_calc_failed == True or self.LunListEmpty == True) and device != resource_disk_device):
                        print("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                        total_used = total_used + int(used) #return in KB
                    #LunList is empty but the device is an actual temporary disk so excluding it
                    elif( (self.size_calc_failed == True or self.LunListEmpty == True) and device == resource_disk_device):
                        print("Device {0} is not included for billing as it is a resource disk, used space in KB : {1} mount point : {2} fstype :{3}".format(device,used,mountpoint,fstype),True)
                        excluded_disks_used = excluded_disks_used + int(used)
                    #Including only the disks which are asked to include (Here LunList can't be empty this case is handled at the CRP end)
                    else:
                        if self.isAnyDiskExcluded == False and device != resource_disk_device:
                            #No disk has been excluded So can include every non resource disk
                            print("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            total_used = total_used + int(used) #return in KB
                        elif self.isAnyDiskExcluded == False and device == resource_disk_device:
                            #excluding resource disk even in the case where all disks are included as it is the actual temporary disk
                            print("Device {0} is not included for billing as it is a resource disk, used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            excluded_disks_used = excluded_disks_used + int(used)
                        elif mountpoint in self.device_mount_points and device != resource_disk_device:
                            print("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                            total_used = total_used + int(used) #return in KB
                        elif device != resource_disk_device and -1 in self.includedLunList:
                            if mountpoint in self.root_mount_points :
                                print("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                total_used = total_used + int(used) #return in KB
                            else:
                                #check for logicalVolumes
                                templgv = device.split("-")
                                if(len(templgv) > 1 and templgv[0] in self.logicalVolume_to_bill):
                                    print("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                    total_used = total_used + int(used) #return in KB
                                else:
                                    print("Device {0} is not included for billing as it is not part of the disks to be included, used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                    excluded_disks_used = excluded_disks_used + int(used)
                        else:
                            # check for logicalVolumes even if os disk is not included
                            templgv = device.split("-")
                            if(len(templgv) > 1 and templgv[0] in self.logicalVolume_to_bill):
                                print("Adding Device name : {0} for billing used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                total_used = total_used + int(used) #return in KB
                            else:
                                print("Device {0} is not included for billing as it is not part of the disks to be included, used space in KB : {1} mount point : {2} fstype : {3}".format(device,used,mountpoint,fstype),True)
                                excluded_disks_used = excluded_disks_used + int(used)
                    if not (isKnownFs or fstype == '' or fstype == None):
                        total_used_unknown_fs = total_used_unknown_fs + int(used)

                index = index + 1

            if not len(unknown_fs_types) == 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("unknownFSTypeInDf",str(unknown_fs_types))
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalUsedunknownFS",str(total_used_unknown_fs))
                print("Total used space in Bytes of unknown FSTypes : {0}".format(total_used_unknown_fs * 1024),True)

            if total_used_temporary_disks != actual_temp_disk_used :
                print("Billing differenct because of incorrect temp disk: {0}".format(str(total_used_temporary_disks - actual_temp_disk_used)))

            if not len(network_fs_types) == 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("networkFSTypeInDf",str(network_fs_types))
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalUsedNetworkShare",str(total_used_network_shares))
                print("Total used space in Bytes of network shares : {0}".format(total_used_network_shares * 1024),True)
            if total_used_gluster !=0 :
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("glusterFSSize",str(total_used_gluster))
            if total_used_temporary_disks !=0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("tempDisksSize",str(total_used_temporary_disks))
            if total_used_ram_disks != 0:
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("ramDisksSize",str(total_used_ram_disks))
            if total_used_loop_device != 0 :
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("loopDevicesSize",str(total_used_loop_device))
            totalSpaceUsed = total_used + excluded_disks_used
            print("TotalUsedSpace ( both included and excluded disks ) in Bytes : {0} , TotalUsedSpaceAfterExcludeLUN in Bytes : {1} , TotalLUNExcludedUsedSpace in Bytes : {2} ".format(totalSpaceUsed *1024 , total_used * 1024 , excluded_disks_used *1024 ),True)
            if total_sd_size != 0 :
                Utils.HandlerUtil.HandlerUtility.add_to_telemetery_data("totalsdSize",str(total_sd_size))
            print("Total sd* used space in Bytes : {0}".format(total_sd_size * 1024),True)
            print("SizeComputationFailedFlag {0}".format(self.size_calc_failed))
            return total_used * 1024,self.size_calc_failed #Converting into Bytes
        except Exception as e:
            errMsg = 'Unable to fetch total used space with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            print(errMsg,True)
            self.size_calc_failed = True
            return 0,self.size_calc_failed
