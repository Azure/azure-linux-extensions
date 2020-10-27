import os
import sys
import re
import subprocess
from subprocess import *
import traceback
from Utils.DiskUtil import DiskUtil

STORAGE_DEVICE_PATH = '/sys/bus/vmbus/devices/'
GEN2_DEVICE_ID = 'f8b3781a-1e82-4818-a1c3-63d806ec15bb'


def read_file(filepath):
	"""
	Read and return contents of 'filepath'.
	"""
	mode = 'rb'
	with open(filepath, mode) as in_file:
		data = in_file.read().decode('utf-8')
		return data

class ResourceDiskUtil(object):

	def __init__(self,patching,logger):
		self.logger = logger
		self.disk_util = DiskUtil(patching,logger)

	
	@staticmethod
	def _enumerate_device_id():
		"""
		Enumerate all storage device IDs.
		Args:
		None
		Returns:
		Iterator[Tuple[str, str]]: VmBus and storage devices.
		"""

		if os.path.exists(STORAGE_DEVICE_PATH):
			for vmbus in os.listdir(STORAGE_DEVICE_PATH):
				deviceid = read_file(filepath=os.path.join(STORAGE_DEVICE_PATH, vmbus, "device_id"))
				guid = deviceid.strip('{}\n')
				yield vmbus, guid


	@staticmethod
	def search_for_resource_disk(gen1_device_prefix, gen2_device_id):
		"""
		Search the filesystem for a device by ID or prefix.
		Args:
		gen1_device_prefix (str): Gen1 resource disk prefix.
		gen2_device_id (str): Gen2 resource device ID.
		Returns:
		str: The found device.
		"""

		device = None
		# We have to try device IDs for both Gen1 and Gen2 VMs.
		#ResourceDiskUtil.logger.log('Searching gen1 prefix {0} or gen2 {1}'.format(gen1_device_prefix, gen2_device_id),True)
		try: # pylint: disable=R1702
			for vmbus, guid in ResourceDiskUtil._enumerate_device_id():
				if guid.startswith(gen1_device_prefix) or guid == gen2_device_id:
					for root, dirs, files in os.walk(STORAGE_DEVICE_PATH + vmbus): # pylint: disable=W0612
						root_path_parts = root.split('/')
						# For Gen1 VMs we only have to check for the block dir in the
						# current device. But for Gen2 VMs all of the disks (sda, sdb,
						# sr0) are presented in this device on the same SCSI controller.
						# Because of that we need to also read the LUN. It will be:
						#   0 - OS disk
						#   1 - Resource disk
						#   2 - CDROM
						if root_path_parts[-1] == 'block' and ( # pylint: disable=R1705
								guid != gen2_device_id or
								root_path_parts[-2].split(':')[-1] == '1'):
							device = dirs[0]
							return device
						else:
							# older distros
							for d in dirs: # pylint: disable=C0103
								if ':' in d and "block" == d.split(':')[0]:
									device = d.split(':')[1]
									return device
		except (OSError, IOError) as exc:
			err_msg='Error getting device for %s or %s: %s , Stack Trace: %s' % (gen1_device_prefix, gen2_device_id, str(exc),traceback.format_exc())
		return None

	def device_for_ide_port(self):
		"""
		Return device name attached to ide port 'n'.
		gen1 device prefix is the prefix of the file name in which the resource disk partition is stored eg sdb
		gen1 is for new distros
		In old distros the directory name which contains resource disk partition is assigned to gen2 device id
		"""
		g0 = "00000000"
		gen1_device_prefix = '{0}-0001'.format(g0)
		self.logger.log('Searching gen1 prefix {0} or gen2 {1}'.format(gen1_device_prefix, GEN2_DEVICE_ID),True)
		device = self.search_for_resource_disk(
			gen1_device_prefix=gen1_device_prefix,
			gen2_device_id=GEN2_DEVICE_ID
		)
		self.logger.log('Found device: {0}'.format(device),True)
		return device

	def get_mount_point(self, mountlist, device):
		"""
		Example of mountlist:
			/dev/sda1 on / type ext4 (rw)
			proc on /proc type proc (rw)
			sysfs on /sys type sysfs (rw)
			devpts on /dev/pts type devpts (rw,gid=5,mode=620)
			tmpfs on /dev/shm type tmpfs
			(rw,rootcontext="system_u:object_r:tmpfs_t:s0")
			none on /proc/sys/fs/binfmt_misc type binfmt_misc (rw)
			/dev/sdb1 on /mnt/resource type ext4 (rw)
		"""
		if (mountlist and device):
			for entry in mountlist.split('\n'):
				if(re.search(device, entry)):
					tokens = entry.split()
					#Return the 3rd column of this line
					return tokens[2] if len(tokens) > 2 else None
		return None

	def get_resource_disk_mount_point(self,option=1): # pylint: disable=R0912,R0914
		try:
			"""
			if option = 0 then partition will be returned eg sdb1
			if option = 1 then mount point will be returned eg /mnt/resource
			"""
			device = self.device_for_ide_port()
			if device is None:
				self.logger.log('unable to detect disk topology',True,'Error')

			if device is not None:
				partition = "{0}{1}".format(device,"1")  #assuming only one resourde disk partition
			else:
				partition=""

			self.logger.log(("Resource disk partition: {0} ",partition),True)
			if(option==0):
				return partition

			#p = Popen("mount", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			#mount_list, err = p.communicate()
			mount_list = self.disk_util.get_mount_output()

			if(mount_list is not None):
				mount_point = self.get_mount_point(mountlist = mount_list, device = device)
				self.logger.log(("Resource disk [{0}] is mounted [{1}]",partition,mount_point),True)
				if mount_point:
					return mount_point
			return None
		except Exception as e:
			err_msg='Cannot get Resource disk partition, Exception %s, stack trace: %s' % (str(e), traceback.format_exc())
			self.logger.log(err_msg, True, 'Error')
			return None
