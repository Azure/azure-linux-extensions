#!/usr/bin/env python

import time
import os
import threading
import signal
import sys
import json
from Utils.WAAgentUtil import waagent
from Utils import HandlerUtil
import datetime
from common import CommonVariables
import subprocess
import traceback
from datetime import datetime

IS_PYTHON3 = sys.version_info[0] == 3
if IS_PYTHON3:
    import configparser as ConfigParsers
else:
    import ConfigParser as ConfigParsers

if IS_PYTHON3:
    from urllib import request
else:
    import urllib2 as request

if IS_PYTHON3:
    from urllib.error import HTTPError
else:
    from urllib2 import HTTPError

if IS_PYTHON3:
    import urllib.parse as urllib
else:
    import urllib


SCRIPT_DIR=os.path.dirname(os.path.realpath(__file__))
BASE_URI="http://168.63.129.16"
STORAGE_DEVICE_PATH = '/sys/bus/vmbus/devices/'
GEN2_DEVICE_ID = 'f8b3781a-1e82-4818-a1c3-63d806ec15bb'
# LOCK_FILE_DIR="/etc/azure/MicrosoftRecoverySvcsSafeFreezeLock"
# LOCK_FILE="/etc/azure/MicrosoftRecoverySvcsSafeFreezeLock/SafeFreezeLockFile"
# LOCK_FILE_NAME="SafeFreezeLockFile"

SNAPSHOT_INPROGRESS = False
    
class HandlerContext:
    def __init__(self,name):
        self._name = name
        self._version = '0.0'
        return

def read_file(filepath):
    """
    Read and return contents of 'filepath'.
    """
    mode = 'rb'
    with open(filepath, mode) as in_file:
        data = in_file.read().decode('utf-8')
        return data

class Handler:
    _log = None
    _error = None
    def __init__(self, log, error, short_name):
        self._context = HandlerContext(short_name)
        self._log = log
        self._error = error
        self.eventlogger = None
        self.log_message = ""
        handler_env_file = './HandlerEnvironment.json'
        if not os.path.isfile(handler_env_file):
            self.error("[handle_host_daemon.py] -> Unable to locate " + handler_env_file)
            return None
        ctxt = waagent.GetFileContents(handler_env_file)
        if ctxt == None :
            self.error("[handle_host_daemon] -> Unable to read " + handler_env_file)
        try:
            handler_env = json.loads(ctxt)
        except:
            pass
        if handler_env == None :
            self.log("JSON error processing " + handler_env_file)
            return None
        if type(handler_env) == list:
            handler_env = handler_env[0]
        self._context._name = handler_env['name']
        self._context._version = str(handler_env['version'])
        self._context._config_dir = handler_env['handlerEnvironment']['configFolder']
        self._context.log_dir = handler_env['handlerEnvironment']['logFolder']
        self._context.log_file = os.path.join(self._context.log_dir,'host_based_extension.log')
        self.logging_file=self._context.log_file

    def _get_log_prefix(self):
        return '[%s-%s]' % (self._context._name, self._context._version)

    def get_value_from_configfile(self, key):
        value = None
        configfile = '/etc/azure/vmbackup.conf'
        try :
            if os.path.exists(configfile):
                config = ConfigParsers.ConfigParser()
                config.read(configfile)
                if config.has_option('SnapshotThread',key):
                    value = config.get('SnapshotThread',key)
        except Exception as e:
            pass
        return value

    def get_strvalue_from_configfile(self, key, default):
        value = self.get_value_from_configfile(key)
        if value == None or value == '':
            value = default
        try :
            value_str = str(value)
        except ValueError :
            self.log('Not able to parse the read value as string, falling back to default value', 'Warning')
            value = default
        return value

    def get_intvalue_from_configfile(self, key, default):
        value = default
        value = self.get_value_from_configfile(key)
        if value == None or value == '':
            value = default
        try :
            value_int = int(value)
        except ValueError :
            self.log('Not able to parse the read value as int, falling back to default value', 'Warning')
            value = default

        return int(value)

    def log(self, message, level='Info'):
        print("[Handler.log] -> Level: {} -> {}".format(level, message))
        try:
            self.log_with_no_try_except(message, level)
        except IOError:
            pass
        except Exception as e:
            try:
                errMsg = str(e) + 'Exception in hutil.log'
                self.log_with_no_try_except(errMsg, 'Warning')
            except Exception as e:
                pass

    def log_with_no_try_except(self, message, level='Info'):
        WriteLog = self.get_strvalue_from_configfile('WriteLog','True')
        if (WriteLog == None or WriteLog == 'True'):
            if sys.version_info > (3,):
                if self.logging_file is not None:
                    self.log_py3(message)
                    if self.eventlogger != None:
                        self.eventlogger.trace_message(level, message)
                else:
                    pass
            else:
                self._log(self._get_log_prefix() + message)
                if self.eventlogger != None:
                    self.eventlogger.trace_message(level, message)
            message = "{0}  {1}  {2} \n".format(str(datetime.datetime.utcnow()) , level , message)
        self.log_message = self.log_message + message

    def log_py3(self, msg):
        if type(msg) is not str:
            msg = str(msg, errors="backslashreplace")
        msg = str(datetime.datetime.utcnow()) + " " + str(self._get_log_prefix()) + msg + "\n"
        try:
            with open(self.logging_file, "a+") as C :
                C.write(msg)
        except IOError:
            pass

    def error(self, message):
        self._error(self._get_log_prefix() + message) 


class InvalidSnapshotRequestInitError(Exception):
    def __init__():
        super().__init__("Snapshot request object intialized incorrectly")

# class AcquireSnapshotLockError(Exception):
#     def __init__():
#         super().__init__("Failed to acquire snapshot lock")

class GetMountsError(Exception):
    def __init__(message = ""):
        super().__init__("[SnapshotRequest.get_mounts] -> failed: {}".format(message))

def print_from_thread(msg):
    os.write(sys.stdout.fileno(), msg.encode("utf-8"))

def thread_for_binary(self,args):
    print_from_thread("[FreezeHandler.thread_for_binary] -> Thread for binary is called: {}\n".format(args))
    time.sleep(3)
    print_from_thread("[FreezeHandler.thread_for_binary] -> Waited in thread for 3 seconds\n")
    print_from_thread("[FreezeHandler.thread_for_binary] -> ****** 1. Starting Freeze Binary \n")
    self.child = subprocess.Popen(args,stdout=subprocess.PIPE)
    print_from_thread("Binary subprocess Created\n")

class FreezeHandler(object):
    def __init__(self,handler):
        # sig_handle valid values(0:nothing done,1: freezed successfully, 2:freeze failed)
        self.sig_handle = 0
        self.child = None
        self.handler = handler 

    def sigusr1_handler(self, signal, frame):
        print_from_thread('[FreezeHandler.sigusr1_handler] -> freezed\n')
        print_from_thread("[FreezeHandler.sigusr1_handler] -> ****** 4. Freeze Completed (Signal=1 received)\n")
        self.sig_handle=1

    def sigchld_handler(self, signal, frame):
        print_from_thread('[FreezeHandler.sigchld_handler] -> some child process terminated\n')
        if(self.child is not None and self.child.poll() is not None):
            print_from_thread("[FreezeHandler.sigchld_handler] -> binary child terminated\n")
            print_from_thread("[FreezeHandler.sigchld_handler] -> ****** 9. Binary Process completed (Signal=2 received)\n")
            self.sig_handle=2

    def reset_signals(self):
        self.sig_handle = 0
        self.child = None

    def startproc(self,args):
        binary_thread = threading.Thread(target=thread_for_binary, args=[self, args])
        binary_thread.start()

        SafeFreezeWaitInSecondsDefault = 66

        proc_sleep_time = self.handler.get_intvalue_from_configfile('SafeFreezeWaitInSeconds',SafeFreezeWaitInSecondsDefault)
        
        for i in range(0,(int(proc_sleep_time/2))):
            if(self.sig_handle==0):
                print("[FreezeHandler.startproc] -> inside loop with sig_handle "+str(self.sig_handle))
                time.sleep(2)
            else:
                break
        print("[FreezeHandler.startproc] -> Binary output for signal handled: "+str(self.sig_handle))
        return self.sig_handle

    def signal_receiver(self):
        signal.signal(signal.SIGUSR1,self.sigusr1_handler)
        signal.signal(signal.SIGCHLD,self.sigchld_handler)

class SnapshotRequest:
    def __init__(self, handler, data):
        global SNAPSHOT_INPROGRESS, BASE_URI, GEN2_DEVICE_ID
        self.freeze_handler = FreezeHandler(handler)
        self.freeze_start = datetime.utcnow()
        self.freeze_safe_active = False
        if isinstance(handler, Handler):
            self.handler = handler
            # MY_PATCHING, PATCH_CLASS_NAME, ORIG_DISTRO = GetMyPatching(handler)
        else:
            raise InvalidSnapshotRequestInitError
        if "snapshotId" in data and isinstance(data["snapshotId"], str):
            self.snapshotId = data["snapshotId"]
        else:
            raise InvalidSnapshotRequestInitError
        
        if "luns" in data and isinstance(data["luns"], list):
            self.luns = data["luns"]
        # else:
        #     raise InvalidSnapshotRequestInitError
        
        if "extensionSettings" in data and isinstance(data["extensionSettigns"], dict):
            self.extensionSettings = {}
            es = data["extensionSettings"]
            if "public" in es and isinstance(es["public"], dict):
                self.extensionSettings["public"] = es["public"]
            else:
                self.extensionSettings["public"] = {}
            if "protected" in es and isinstance(es["protected"], dict):
                self.extensionSettings["protected"] = {}
                pro = es["protected"]
                if "loggingBlobSasUri" in pro and isinstance(pro["loggingBlobSasUri"], str):
                    self.extensionSettings.protected["loggingBlobSasUri"] = pro["loggingBlobSasUri"]
                # else:
                #     raise InvalidSnapshotRequestInitError
                if "statusBlobSasUri" in pro and isinstance(pro["statusBlobSasUri"], str):
                    self.extensionSettings.protected["statusBlobSasUri"] = pro["statusBlobSasUri"]
                # else:
                #     raise InvalidSnapshotRequestInitError
            # else:
            #     raise InvalidSnapshotRequestInitError
            
            if "ProtectedSettingsCertThumbprint" in data and isinstance(data["ProtectedSettingsCertThumbprint"], str):
                self.ProtectedSettingsCertThumbprint = data["ProtectedSettingsCertThumbprint"]
            # else:
            #     raise InvalidSnapshotRequestInitError
        self.__data = data

    # def acquire_snapshot_lock(self):
    #     try:
    #         if not os.path.isdir('/etc/azure'):
    #             os.mkdir('/etc/azure')
    #         if not os.path.isdir(LOCK_FILE_DIR):
    #             if not os.path.isfile(LOCK_FILE_DIR):
    #                 os.mkdir(LOCK_FILE_DIR)
    #             else:
    #                 os.remove(LOCK_FILE_DIR)
    #                 os.mkdir(LOCK_FILE_DIR)
    #         self.safeFreezelockFile = open(LOCK_FILE,"w")
    #         try:
    #             fcntl.lockf(self.safeFreezelockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    #             self.isAcquiredLock = True
    #             return True
    #         except Exception as e:
    #             self.handler.log("[lock_snapshot_file] -> fcntl.lockf has failed: ", e)
    #             self.safeFreezelockFile.close()
    #     except Exception as e:
    #         self.handler.log("[lock_snapshot_file] -> Unexpected error occured: ", e)
    #     return False

    # def release_snapshot_lock(self):
    #     try:
    #         if (self.isAquireLock == True):
    #             try:
    #                 fcntl.lockf(self.safeFreezelockFile, fcntl.LOCK_UN)
    #                 self.safeFreezelockFile.close()
    #             except Exception as e:
    #                 self.handler.log("Failed to unlock: %s, stack trace: %s" % (str(e), traceback.format_exc()),True)
    #         try:
    #             os.remove(LOCK_FILE)
    #         except Exception as e:
    #             self.handler.log(
    #                 "Failed to delete %s file:\nException:\n%s\nStack Trace:\n%s" %
    #                   LOCK_FILE, str(e), traceback.format_exc())
    #     except Exception as e:
    #         self.handler.log("[release_snapshot_lock] -> unexpected error occurred: ", e)
    #     return False

    # Ignores usb devices
    # TODO: suppport lvm setup
    def get_block_devices(self):
        p1 = subprocess.Popen(["lsblk", "-dnl", "-o", "NAME"], stdout=subprocess.PIPE)
        p2 = subprocess.check_output(["grep", "-E", "(sd|nvme)"], stdin=p1.stdout).decode("utf-8")
        p1.stdout.close()
        disks = []
        for x in p2.split("\n"):
            # print("device: {}".format(x))
            if not x.strip():
                continue
            if not self.is_usb("/dev/{}".format(x)):
                disks.append(x)
        return disks
    
    def is_usb(self, device):
        # lsblk -dnl -o NAME | grep 'sd'
        # udevadm info /dev/sda --query=property | grep ID_BUS
        p1 = subprocess.Popen(["udevadm", "info", device, "--query=property"], stdout=subprocess.PIPE)
        p2 = subprocess.check_output(["grep", 'ID_BUS'], stdin=p1.stdout).decode("utf-8")
        p1.stdout.close()
        return p2.endswith("=usb")
    
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
            for vmbus, guid in SnapshotRequest._enumerate_device_id():
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
        self.handler.log(
            '[SnapshostRequest.device_for_ide_port] -> Searching gen1 prefix {0} or gen2 {1}'.format(
                gen1_device_prefix, GEN2_DEVICE_ID
        ))
        device = self.search_for_resource_disk(
        	gen1_device_prefix=gen1_device_prefix,
        	gen2_device_id=GEN2_DEVICE_ID
        )
        self.handler.log('[SnapshotRequest.device_for_ide_port] -> Found device: {0}'.format(device))
        return device

    def get_resource_disk_mount_point(self,option=1): # pylint: disable=R0912,R0914
        try:
            """
            if option = 0 then partition will be returned eg sdb1
            if option = 1 then mount point will be returned eg /mnt/resource
            """
            device = self.device_for_ide_port()
            if device is None:
                self.handler.log('unable to detect disk topology',True,'Error')
            
            partition = None
            if device is not None:
                partition = "{0}{1}".format(device,"1")  #assuming only one resourde disk partition
            self.handler.log("Resource disk partition: {0} ".format(partition),True)
            if(option==0):
                return partition
            
            # find name of mount using:
            # grep -E "^/dev/sdb1" /proc/mounts | awk '{print $2}'
            # print("Found partition: {}".format(partition))
            if partition is not None:
                p1 = subprocess.Popen(["grep", "-E", "^/dev/{}".format(partition), "/proc/mounts"], stdout=subprocess.PIPE)
                p2 = subprocess.check_output(["awk", '{print $2}'], stdin=p1.stdout).decode("utf-8")
                p1.stdout.close()
                v = [x for x in p2.split("\n") if x.strip()]
                if len(v) > 0:
                    # print("Returning v[0]: {}".format(v[0]))
                    return v[0]
        except Exception as e:
            self.handler.log(
                    "[SnapshotRequest.get_resource_disk_mountpoint] -> unexpected error occured: {}\n{}".format(e, traceback.format_exc())
            )
        return None

    def get_mounts(self):
        try:
            resource_mount = self.get_resource_disk_mount_point()
            p1 = subprocess.Popen(["mount", "-l"], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["grep", "-E", "(ext4|ext3|btrfs|xfs)"], stdin=p1.stdout, stdout=subprocess.PIPE)
            p3 = subprocess.check_output(["awk", '{print $1" "$3}'], stdin=p2.stdout).decode("utf-8")
            p1.stdout.close()
            p2.stdout.close()
            # print("p3: {}".format(p3))
            disks = self.get_block_devices() 
            # print("disks: {}".format(disks))
            def is_valid_mount(partition,mount_point):
                if resource_mount is not None and mount_point.strip() == resource_mount:
                    return False
                # lsblk -ndo pkname /dev/sda1
                disk = subprocess.check_output(["lsblk", "-ndo", "pkname", partition]).decode("utf-8")
                disk = " ".join(disk.split()) # removing any trailing or preceding newlines
                # print("[is_valid_disk] -> if disk: {} exists in list: {}".format(disk, disks))
                if disk not in disks:
                    return False
                return True
            mounts = []
            for m in p3.split("\n"):
                if not m.strip():
                    continue
                m = " ".join(m.split()) # removing any preceding or trailing new lines
                v = m.split()
                # print("Post split: {}".format(v))
                if len(v) != 2:
                    continue 
                partition = v[0]
                mount_point = v[1]
                # print("[get_mounts] -> Checking mount: {}".format(mount_point))
                # print("[get_mounts] -> Checking partition: {}".format(partition))
                if not is_valid_mount(partition, mount_point):
                    continue
                mounts.append(mount_point)
            print("Mounts: {}".format(mounts))
            return mounts
        except Exception as e:
            self.handler.log("[SnapshotRequest.get_mounts] -> Unexpected error: {}".format(e))
            raise GetMountsError(traceback.format_exc())

    def safefreeze_path(self):
        p = os.path.join(os.getcwd(),os.path.dirname(__file__),"safefreeze/bin/safefreeze")
        machine = os.uname()[-1]
        if IS_PYTHON3:
            machine = os.uname().machine
        if machine is not None and (machine.startswith("arm64") or machine.startswith("aarch64")):
            p = "safefreezeArm64/bin/safefreeze"
        return p
    
    def log_binary_output(self):
        print(
            "[SnapshotRequest.log_binary_output] -> ============== Binary output traces start ================= "
        )
        while True:
            line=self.freeze_handler.child.stdout.readline()
            if IS_PYTHON3:
                line = str(line, encoding='utf-8', errors="backslashreplace")
            else:
                line = str(line)
            if("[SnapshotRequest.log_binary_output] -> Failed to open:" in line):
                self.mount_open_failed = True
            if(line != ''):
                self.handler.log(line.rstrip(), True)
            else:
                break
        print(
            "[SnapshotRequest.log_binary_output] -> ============== Binary output traces end ================= "
        )

    def freeze_safe(self, args):
        errors = []
        error_codes = []
        timedout = False
        try:
            self.freeze_handler.reset_signals()
            self.freeze_handler.signal_receiver()
            sig_handle = self.freeze_handler.startproc(args)
            # self.handler.log(
            #     "[SnapshotRequest.freeze_safe] -> freeze_safe after returning from startproc : sig_handle={}".format(str(sig_handle))
            # )
            print("[SnapshotRequest.freeze_safe] -> freeze_safe after returning from startproc : sig_handle={}".format(str(sig_handle)))
            if(sig_handle != 1):
                if (self.freeze_handler.child is not None):
                    print("[SnapshotRequest.freeze_safe] -> calling log_binary_output")
                    self.log_binary_output()
                if (sig_handle == 0):
                    timedout = True
                    error_msg="freeze timed-out"
                    errors.append(error_msg)
                    error_codes.append("FREEZE_TIMED_OUT")
                    self.handler.log(error_msg)
                # elif (self.mount_open_failed == True):
                #     error_msg=CommonVariables.unable_to_open_err_string
                #     errors.append(error_msg)
                #     self.handler.log(error_msg)
                # elif (self.isAquireLockSucceeded == False):
                #     error_msg="Mount Points already freezed by some other processor"
                #     errors.append(error_msg)
                #     self.handler.log(error_msg)
                else:
                    error_msg="freeze failed for some mount"
                    errors.append(error_msg)
                    error_codes.append("INCOMPLETE_FREEZE")
                    self.handler.log(error_msg)
        except Exception as e:
            # self.logger.enforce_local_flag(True)
            error_msg='freeze failed for some mount with exception, Exception %s, stack trace: %s' % (str(e), traceback.format_exc())
            errors.append(error_msg)
            error_codes.append("UNEXPECTED_FREEZE_EXC")
            self.handler.log(error_msg)
        finally:
            self.freeze_start_time = datetime.utcnow()
        return errors, error_codes, timedout

    def thaw_safe(self):
        errors = []
        unable_to_sleep = False
        try:
            if not self.freeze_safe_active:
                self.freeze_end_time = datetime.utcnow()
                return errors, unable_to_sleep
            if(self.freeze_handler.child is None):
                print("[SnapshotRequest.thaw_safe] -> child already completed")
                print("[SnapshotRequest.thaw_safe] -> ****** 7. Error - Binary Process Already Completed")
                error_msg = 'snapshot result inconsistent'
                errors.append(error_msg)
            elif(self.freeze_handler.child.poll() is None):
                print("[SnapshotRequest.thaw_safe] -> child process still running")
                print("[SnapshotRequest.thaw_safe] -> ****** 7. Sending Thaw Signal to Binary")
                self.freeze_handler.child.send_signal(signal.SIGUSR1)
                
                # Will try for 30 seconds to see if freeze process has stopped
                for i in range(0,30):
                    if(self.freeze_handler.child.poll() is None):
                        print("child still running sigusr1 sent")
                        time.sleep(1)
                    else:
                        break
                print("[SnapshotRequest.thaw_safe] -> calling log_binary_output: 1")
                self.log_binary_output()
                if(self.freeze_handler.child.returncode != 0):
                    error_msg = '[SnapshotRequest.thaw_safe] -> snapshot result inconsistent as child returns with failure'
                    errors.append(error_msg)
                    print(error_msg, True, 'Error')
            else:
                self.handler.log("[SnapshotRequest.thaw_safe] -> Binary output after process end when no thaw sent: ", True)
                if(self.freeze_handler.child.returncode == 2):
                    error_msg = '[SnapshotRequest.thaw_safe] -> Unable to execute sleep'
                    errors.append(error_msg)
                    unable_to_sleep = True
                else:
                    error_msg = '[SnapshotRequest.thaw_safe] -> snapshot result inconsistent'
                    errors.append(error_msg)
                print("[SnapshotRequest.thaw_safe] -> calling log_binary_output: 2")
                self.log_binary_output()
                print(error_msg, True, 'Error')
        finally:
            self.freeze_end_time = datetime.utcnow()
        return errors, unable_to_sleep

    # Uses safe_freeze binary which depends on fsfreeze
    # TODO: support LVM when present
    def freeze_mounts(self):
        errors = []
        error_codes = []
        try:
            timeout = self.handler.get_intvalue_from_configfile('timeout','60')
            args = [self.safefreeze_path(), str(timeout)]
            mounts = self.get_mounts()
            if len(mounts) == 0:
                self.handler.log("[SnapshotRequest.freeze_mounts] -> nothing to freeze")
                return False
            for mount in mounts:
                args.append(mount)
            errors, error_codes, timedout = self.freeze_safe(args)
            if len(errors) == 0 and not timedout:
                self.freeze_start_time = datetime.utcnow()
                self.freeze_safe_active = True
        except GetMountsError as gme:
            self.handler.log("[SnapshotRequest.freeze_mounts] -> get_mounts failed: {}\n{}".format(gme, traceback.format_exc()))
        except Exception as e:
            self.handler.log("[SnapshotRequest.freeze_mounts] -> unexpected error occured: {}\n{}".format(e, traceback.format_exc()))
        return errors, error_codes

    def start_snapshot(self, error_code = None, error_message = None):
        print("[SnapshotRequest.start_snapshot] -> Fired")
        errors = []
        try:
            payload = {
                "snapshotId": self.snapshotId,
                "errMsg": ""
            }
            if error_code is not None:
                payload["error"] = {
                    "code": error_code if isinstance(error_code, str) else "",
                    "message": error_message if isinstance(error_message, str) else "",
                }
                payload["errMsg"] = error_message if isinstance(error_message, str) else ""
            
            # if IS_PYTHON3:
            #     data = urllib.urlencode(payload).encode("utf-8")
            # else:
            #     data = urllib.urlencode(payload)
            # print("[SnapshotRequest.start_snapshot] -> Data:{}".format(data))

            if IS_PYTHON3:
                data = json.dumps(payload).encode("utf-8")
                print("[SnapshotRequest.start_snapshot] -> Data: {}".format(data))
                r = request.Request(
                    url = "{}/machine/plugins?comp=xdisksvc&type=startsnapshot".format(BASE_URI),
                    headers = {
                        "Content-Type": "application/json; charset=utf-8",
                        "Content-Length": len(data),
                    }
                )
            else:
                data = json.dumps(payload)
                print("[SnapshotRequest.start_snapshot] -> Data: {}".format(data))
                r = request.Request(
                    url = "{}/machine/plugins?comp=xdisksvc&type=startsnapshot".format(BASE_URI),
                    headers = {
                        "Content-Type": "application/json; charset=utf-8"
                    }
                )
            conn = request.urlopen(r, timeout = 10, data = data)
            print("[SnapshotRequest.start_snapshot] -> Request: {}".format(r))
            # if IS_PYTHON3:
            #     conn = request.urlopen(r, timeout = 10, data = data)
            # else:
            #     conn = request.urlopen(r, timeout = 10)
            if conn.status != 200:
                resp = conn.read()
                print("[SnapshotRequest.start_snapshot] -> unexpected status code:{}, Body: {}".format(conn.status, resp))
                errors.append("STARTSNAP_UNEXPECTED_STATUS_{}".format(conn.status))
        except HTTPError as herr:
            print("[SnapshotRequest.start_snapshot] -> startsnapshot request failed with status: {}, reason: {}".format(herr.code, herr.reason))
            errors.append("STARTSNAP_HTTP_ERR")
        except Exception as e:
            print("[SnapshotRequest.start_snapshot] -> unexpected error occured: {}\n{}".format(e, traceback.format_exc()))
            errors.append("STARTSNAP_UNEXPECTED_EXC")
        return errors

    def end_snapshot(self, payload):
        errors = []
        try:

            # if IS_PYTHON3:
            #     data = urllib.urlencode(payload).encode("utf-8")
            # else:
            #     data = urllib.urlencode(payload)
            # print("[SanpshotRequest.end_snapshot] -> Data:{}".format(data))
            if IS_PYTHON3:
                data = json.dumps(payload).encode("utf-8")
                print("[SnapshotRequest.end_snapshot] -> Data: {}".format(data))
                r = request.Request(
                    url = "{}/machine/plugins?comp=xdisksvc&type=publishsnapshot".format(BASE_URI),
                    headers = {
                        "Content-Type": "application/json",
                        "Content-Length": len(data)
                    }
                )
            else:
                data = json.dumps(payload)
                print("[SnapshotRequest.end_snapshot] -> Data: {}".format(data))
                r = request.Request(
                    url = "{}/machine/plugins?comp=xdisksvc&type=publishsnapshot".format(BASE_URI),
                    headers = {
                        "Content-Type": "application/json"
                    }
                )

            conn = request.urlopen(r, timeout = 10, data = data)
            # if IS_PYTHON3:
            #     conn = request.urlopen(r, timeout = 10, data = data)
            # else:
            #     conn = request.urlopen(r, timeout = 10)
            if conn.status != 200:
                resp = conn.read()
                print("[SnapshotRequest.end_snapshot] -> unexpected status code: {}, Body: {}".format(conn.status, resp))
                errors.append("ENDSNAP_UNEXPECTED_STATUS_{}".format(conn.status))
        except HTTPError as herr:
            print("[SnapshotRequest.end_snapshot] -> unexpected status code: {}, reason: {}".format(herr.code, herr.reason))
            errors.append("ENDSNAP_UNEXPECTED_STATUS_{}".format(herr.code))
        except Exception as e:
            print("[SnapshotRequest.end_snapshot] -> unexpected error occured: {}\n{}".format(e, traceback.format_exc()))
            errors.append("ENDSNAP_UNEXPECTED_EXC")
        return errors

    def take_snapshot(self):
        # self.freeze_start = datetime.utcnow()
        print("[SnapshotRequest.take_snapshot] -> Fired")
        frozen_at = 0
        call_remote_end = 0
        remote_call_success = False
        snapshot_error_code = None
        snapshot_error_msg = None

        try:
            errors, error_codes = self.freeze_mounts()
            x_errors = []
            if len(errors) > 0:
                print("[Snapshot_Request.take_snapshot] -> self.freeze_mounts() failed")
                print("{}".format("\n".join(errors)))
                x_errors = self.start_snapshot(error_code = error_codes[0], error_message = errors[0])
                snapshot_error_code = error_codes[0]
                snapshot_error_msg = errors[0]
            else:
                print("[Snapshot_Request.take_snapshot] -> self.freeze_mounts() success")
                frozen_at = datetime.utcnow()
                x_errors = self.start_snapshot()
            if len(x_errors) > 0:
                print("[Snapshot_Request.take_snapshot] -> calling xdisksvc failed with: {}".format(x_errors[0]))
                snapshot_error_code = x_errors[0]
                snapshot_error_msg = snapshot_error_code
            else:
                print("[Snapshot_Request.take_snapshot] -> calling xdisksvc succeeded")
                remote_call_success = True
        except Exception as e:
            print("[SnapshotRequest.take_snapshot] -> unexpected exception: {}\n{}".format(e, traceback.format_exc()))
            snapshot_error_code = "UNEXPECTED_SNAPSHOT_EXC"
            snapshot_error_msg = str(e)
        finally:
            call_remote_end = datetime.utcnow()
            self.thaw_safe()
            print("[SnapshotRequest.take_snapshot] -> thaw_safe executed successfully")
        
        print("[SnapshotRequest.take_snapshot] -> Outta try catch!")
        body = {
            "snapshotId": self.snapshotId,
            "errMsg": "",
            # "consistencyMode": "App",
        }
        if remote_call_success and (call_remote_end.timestamp() - frozen_at.timestamp()) < 9:
            print("[SanpshotRequest.take_snapshot] -> app consistency verified")
        else:
            print("[SnapshotRequest.take_snapshot] -> app consistency validation failed")
            body["error"] = {
                "code": snapshot_error_code,
                "message": snapshot_error_msg
            }
            body["errMsg"] = snapshot_error_msg
        self.end_snapshot(body)

def get_snapshot_requests(handler):
    global BASE_URI
    res = {
        "statusCode": 0,
        "data": {},
    }
    try:
        conn = request.urlopen(BASE_URI + "/machine/plugins?comp=xdisksvc&type=checkforsnapshot", timeout = 10)
        res["statusCode"] = conn.status
        if res["statusCode"] == 200:
            res["data"] = json.loads(conn.read())
            return res
    except HTTPError as herr:
        res["statusCode"] = herr.code
    except Exception as e:
        handler.log("Exception making a http request", e)
    return res

def take_new_snapshot(handler, data):
    try:
        sr = SnapshotRequest(handler, data)
        sr.take_snapshot()
    except InvalidSnapshotRequestInitError:
        handler.log("[take_new_snapshot] -> SnapshotRequest object initialized with invalid data: ", data)
    except Exception as e:
        handler.log("[take_new_snapshot] -> Unexpected error occurred: ", e)

def main():
    global SCRIPT_DIR
    HandlerUtil.waagent.LoggerInit('/dev/console','/dev/stdout')
    handler = Handler(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    starttime = time.time()
    while True:
        try:
            res = get_snapshot_requests(handler)
            print("[main] -> res: {}".format(res))
            if res["statusCode"] == 200:
                take_new_snapshot(handler, res["data"])
            elif res["statusCode"] == 404:
                handler.log("[main] -> no new snapshot requests at this time")
            else:
                handler.log("[main] -> invalid response code: ", res["statusCode"])
        except Exception as e:
            handler.log("[main] -> Unexpected expcetion occured", e)
        time.sleep(300.0 - ((time.time() - starttime) % 300.0))

if __name__ == '__main__' :
    main()
