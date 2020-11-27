#
# Handler library for Linux IaaS
#
# Copyright 2014 Microsoft Corporation
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

"""
JSON def:
HandlerEnvironment.json
[{
  "name": "ExampleHandlerLinux",
  "seqNo": "seqNo",
  "version": "1.0",
  "handlerEnvironment": {
    "logFolder": "<your log folder location>",
    "configFolder": "<your config folder location>",
    "statusFolder": "<your status folder location>",
    "heartbeatFile": "<your heartbeat file location>",
    
  }
}]

Example ./config/1.settings
"{"runtimeSettings":[{"handlerSettings":{"protectedSettingsCertThumbprint":"1BE9A13AA1321C7C515EF109746998BAB6D86FD1","protectedSettings":
"MIIByAYJKoZIhvcNAQcDoIIBuTCCAbUCAQAxggFxMIIBbQIBADBVMEExPzA9BgoJkiaJk/IsZAEZFi9XaW5kb3dzIEF6dXJlIFNlcnZpY2UgTWFuYWdlbWVudCBmb3IgR+nhc6VHQTQpCiiV2zANBgkqhkiG9w0BAQEFAASCAQCKr09QKMGhwYe+O4/a8td+vpB4eTR+BQso84cV5KCAnD6iUIMcSYTrn9aveY6v6ykRLEw8GRKfri2d6tvVDggUrBqDwIgzejGTlCstcMJItWa8Je8gHZVSDfoN80AEOTws9Fp+wNXAbSuMJNb8EnpkpvigAWU2v6pGLEFvSKC0MCjDTkjpjqciGMcbe/r85RG3Zo21HLl0xNOpjDs/qqikc/ri43Y76E/Xv1vBSHEGMFprPy/Hwo3PqZCnulcbVzNnaXN3qi/kxV897xGMPPC3IrO7Nc++AT9qRLFI0841JLcLTlnoVG1okPzK9w6ttksDQmKBSHt3mfYV+skqs+EOMDsGCSqGSIb3DQEHATAUBggqhkiG9w0DBwQITgu0Nu3iFPuAGD6/QzKdtrnCI5425fIUy7LtpXJGmpWDUA==","publicSettings":{"port":"3000"}}}]}"


Example HeartBeat
{
"version": 1.0,
    "heartbeat" : {
        "status": "ready",
        "code": 0,
        "Message": "Sample Handler running. Waiting for a new configuration from user."
    }
}
Example Status Report:
[{"version":"1.0","timestampUTC":"2014-05-29T04:20:13Z","status":{"name":"Chef Extension Handler","operation":"chef-client-run","status":"success","code":0,"formattedMessage":{"lang":"en-US","message":"Chef-client run success"}}}]

"""


import os
import os.path
import sys
import re
try:
    import imp as imp
except ImportError:
    import importlib as imp
import base64
import json
import tempfile
import time
from os.path import join
import Utils.WAAgentUtil
from Utils.WAAgentUtil import waagent
import logging
import logging.handlers
try:
        import ConfigParser as ConfigParsers
except ImportError:
        import configparser as ConfigParsers
from common import CommonVariables
import platform
import subprocess
import datetime
import Utils.Status
from MachineIdentity import MachineIdentity
import ExtensionErrorCodeHelper
import traceback

DateTimeFormat = "%Y-%m-%dT%H:%M:%SZ"

class HandlerContext:
    def __init__(self,name):
        self._name = name
        self._version = '0.0'
        return

class HandlerUtility:
    telemetry_data = {} 
    serializable_telemetry_data = []
    ExtErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.success
    SnapshotConsistency = Utils.Status.SnapshotConsistencyType.none
    HealthStatusCode = -1
    def __init__(self, log, error, short_name):
        self._log = log
        self._error = error
        self.log_message = ""
        self._short_name = short_name
        self.patching = None
        self.storageDetailsObj = None
        self.partitioncount = 0
        self.logging_file = None
        self.pre_post_enabled = False

    def _get_log_prefix(self):
        return '[%s-%s]' % (self._context._name, self._context._version)

    def _get_current_seq_no(self, config_folder):
        seq_no = -1
        cur_seq_no = -1
        freshest_time = None
        for subdir, dirs, files in os.walk(config_folder):
            for file in files:
                try:
                    if(file.endswith('.settings')):
                        cur_seq_no = int(os.path.basename(file).split('.')[0])
                        if(freshest_time == None):
                            freshest_time = os.path.getmtime(join(config_folder,file))
                            seq_no = cur_seq_no
                        else:
                            current_file_m_time = os.path.getmtime(join(config_folder,file))
                            if(current_file_m_time > freshest_time):
                                freshest_time = current_file_m_time
                                seq_no = cur_seq_no
                except ValueError:
                    continue
        return seq_no

    def get_last_seq(self):
        if(os.path.isfile('mrseq')):
            seq = waagent.GetFileContents('mrseq')
            if(seq):
                return int(seq)
        return -1

    def exit_if_same_seq(self):
        current_seq = int(self._context._seq_no)
        last_seq = self.get_last_seq()
        if(current_seq == last_seq):
            self.log("the sequence number are same, so skip, current:" + str(current_seq) + "== last:" + str(last_seq))
            self.update_settings_file()
            sys.exit(0)

    def log(self, message,level='Info'):
        try:
            self.log_with_no_try_except(message, level)
        except IOError:
            pass
        except Exception as e:
            try:
                errMsg='Exception in hutil.log'
                self.log_with_no_try_except(errMsg, 'Warning')
            except Exception as e:
                pass

    def log_with_no_try_except(self, message, level='Info'):
        WriteLog = self.get_strvalue_from_configfile('WriteLog','True')
        if (WriteLog == None or WriteLog == 'True'):
            if sys.version_info > (3,):
                if self.logging_file is not None:
                    self.log_py3(message)
                else:
                    pass
            else:
                self._log(self._get_log_prefix() + message)
            message = "{0}  {1}  {2} \n".format(str(datetime.datetime.now()) , level , message)
        self.log_message = self.log_message + message

    def log_py3(self, msg):
        if type(msg) is not str:
            msg = str(msg, errors="backslashreplace")
        msg = str(datetime.datetime.now()) + " " + str(self._get_log_prefix()) + msg + "\n"
        try:
            with open(self.logging_file, "a+") as C :
                C.write(msg)
        except IOError:
            pass

    def error(self, message):
        self._error(self._get_log_prefix() + message)

    def fetch_log_message(self):
        return self.log_message

    def _parse_config(self, ctxt):
        config = None
        try:
            config = json.loads(ctxt)
        except:
            self.error('JSON exception decoding ' + ctxt)
        if config == None:
            self.error("JSON error processing settings file:" + ctxt)
        else:
            handlerSettings = config['runtimeSettings'][0]['handlerSettings']
            if 'protectedSettings' in handlerSettings and \
                    "protectedSettingsCertThumbprint" in handlerSettings and \
                    handlerSettings['protectedSettings'] is not None and \
                    handlerSettings["protectedSettingsCertThumbprint"] is not None:
                protectedSettings = handlerSettings['protectedSettings']
                thumb = handlerSettings['protectedSettingsCertThumbprint']
                cert = waagent.LibDir + '/' + thumb + '.crt'
                pkey = waagent.LibDir + '/' + thumb + '.prv'
                f = tempfile.NamedTemporaryFile(delete=False)
                f.close()
                waagent.SetFileContents(f.name,config['runtimeSettings'][0]['handlerSettings']['protectedSettings'])
                cleartxt = None
                if 'NS-BSD' in platform.system():
                    # base64 tool is not available with NSBSD, use openssl
                    cleartxt = waagent.RunGetOutput(self.patching.openssl_path + " base64 -d -A -in " + f.name + " | " + self.patching.openssl_path + " smime  -inform DER -decrypt -recip " + cert + "  -inkey " + pkey)[1]
                else:
                    cleartxt = waagent.RunGetOutput(self.patching.base64_path + " -d " + f.name + " | " + self.patching.openssl_path + " smime  -inform DER -decrypt -recip " + cert + "  -inkey " + pkey)[1]
                jctxt = {}
                try:
                    jctxt = json.loads(cleartxt)
                except:
                    self.error('JSON exception decoding ' + cleartxt)
                handlerSettings['protectedSettings'] = jctxt
                self.log('Config decoded correctly.')
        return config

    def do_parse_context(self, operation):
        self.operation = operation
        _context = self.try_parse_context()
        getWaagentPathUsed = Utils.WAAgentUtil.GetPathUsed()
        if(getWaagentPathUsed == 0):
            self.log("waagent old path is used")
        else:
            self.log("waagent new path is used")
        if not _context:
            self.log("maybe no new settings file found")
            sys.exit(0)
        return _context

    def try_parse_context(self):
        self._context = HandlerContext(self._short_name)
        handler_env = None
        config = None
        ctxt = None
        code = 0
        try:
            # get the HandlerEnvironment.json.  According to the extension handler
            # spec, it is always in the ./ directory
            self.log('cwd is ' + os.path.realpath(os.path.curdir))
            handler_env_file = './HandlerEnvironment.json'
            if not os.path.isfile(handler_env_file):
                self.error("Unable to locate " + handler_env_file)
                return None
            ctxt = waagent.GetFileContents(handler_env_file)
            if ctxt == None :
                self.error("Unable to read " + handler_env_file)
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
            self._context._log_dir = handler_env['handlerEnvironment']['logFolder']
            self._context._log_file = os.path.join(handler_env['handlerEnvironment']['logFolder'],'extension.log')
            self.logging_file=self._context._log_file
            self._context._shell_log_file = os.path.join(handler_env['handlerEnvironment']['logFolder'],'shell.log')
            self._change_log_file()
            self._context._status_dir = handler_env['handlerEnvironment']['statusFolder']
            self._context._heartbeat_file = handler_env['handlerEnvironment']['heartbeatFile']
            self._context._seq_no = self._get_current_seq_no(self._context._config_dir)
            if self._context._seq_no < 0:
                self.error("Unable to locate a .settings file!")
                return None
            self._context._seq_no = str(self._context._seq_no)
            self.log('sequence number is ' + self._context._seq_no)
            self._context._status_file = os.path.join(self._context._status_dir, self._context._seq_no + '.status')
            self._context._settings_file = os.path.join(self._context._config_dir, self._context._seq_no + '.settings')
            self.log("setting file path is" + self._context._settings_file)
            ctxt = None
            ctxt = waagent.GetFileContents(self._context._settings_file)
            if ctxt == None :
                error_msg = 'Unable to read ' + self._context._settings_file + '. '
                self.error(error_msg)
                return None
            else:
                if(self.operation is not None and self.operation.lower() == "enable"):
                    # we should keep the current status file
                    self.backup_settings_status_file(self._context._seq_no)
            self._context._config = self._parse_config(ctxt)
        except Exception as e:
            errorMsg = "Unable to parse context, error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.log(errorMsg, 'Error')
            raise
        return self._context

    def _change_log_file(self):
        self.log("Change log file to " + self._context._log_file)
        waagent.LoggerInit(self._context._log_file,'/dev/stdout')
        self._log = waagent.Log
        self._error = waagent.Error

    def save_seq(self):
        self.set_last_seq(self._context._seq_no)
        self.log("set most recent sequence number to " + self._context._seq_no)

    def set_last_seq(self,seq):
        waagent.SetFileContents('mrseq', str(seq))


    '''
    Sample /etc/azure/vmbackup.conf
 
    [SnapshotThread]
    seqsnapshot = 1
    isanysnapshotfailed = False
    UploadStatusAndLog = True
    WriteLog = True

    seqsnapshot valid values(0-> parallel snapshot, 1-> programatically set sequential snapshot , 2-> customer set it for sequential snapshot)
    '''

    def get_value_from_configfile(self, key):
        global backup_logger
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
 
    def set_value_to_configfile(self, key, value):
        configfile = '/etc/azure/vmbackup.conf'
        try :
            self.log('setting ' + str(key)  + 'in config file to ' + str(value) , 'Info')
            if not os.path.exists(os.path.dirname(configfile)):
                os.makedirs(os.path.dirname(configfile))
            config = ConfigParsers.RawConfigParser()
            if os.path.exists(configfile):
                config.read(configfile)
                if config.has_section('SnapshotThread'):
                    if config.has_option('SnapshotThread', key):
                        config.remove_option('SnapshotThread', key)
                else:
                    config.add_section('SnapshotThread')
            else:
                config.add_section('SnapshotThread')
            config.set('SnapshotThread', key, value)
            with open(configfile, 'w') as config_file:
                config.write(config_file)
        except Exception as e:
            errorMsg = " Unable to set config file.key is "+ key +"with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.log(errorMsg, 'Warning')
        return value

    def get_machine_id(self):
        machine_id_file = "/etc/azure/machine_identity_FD76C85E-406F-4CFA-8EB0-CF18B123358B"
        machine_id = ""
        try:
            if not os.path.exists(os.path.dirname(machine_id_file)):
                os.makedirs(os.path.dirname(machine_id_file))

            if os.path.exists(machine_id_file):
                file_pointer = open(machine_id_file, "r")
                machine_id = file_pointer.readline()
                file_pointer.close()
            else:
                mi = MachineIdentity()
                machine_id = mi.stored_identity()[1:-1]
                file_pointer = open(machine_id_file, "w")
                file_pointer.write(machine_id)
                file_pointer.close()
        except Exception as e:
            errMsg = 'Failed to retrieve the unique machine id with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg, 'Error')
 
        self.log("Unique Machine Id  : {0}".format(machine_id))
        return machine_id

    def get_total_used_size(self):
        try:
            df = subprocess.Popen(["df" , "-k" , "--output=source,fstype,size,used,avail,pcent,target"], stdout=subprocess.PIPE)
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

            output = df.stdout.read()
            output = output.split("\n")
            total_used = 0
            total_used_network_shares = 0
            total_used_gluster = 0
            network_fs_types = []
            for i in range(1,len(output)-1):
                device, fstype, size, used, available, percent, mountpoint = output[i].split()
                self.log("Device name : {0} fstype : {1} size : {2} used space in KB : {3} available space : {4} mountpoint : {5}".format(device,fstype,size,used,available,mountpoint))
                if "fuse" in fstype.lower() or "nfs" in fstype.lower() or "cifs" in fstype.lower():
                    if fstype not in network_fs_types :
                        network_fs_types.append(fstype)
                    self.log("Not Adding as network-drive, Device name : {0} used space in KB : {1} fstype : {2}".format(device,used,fstype))
                    total_used_network_shares = total_used_network_shares + int(used)
                elif (mountpoint.startswith('/run/gluster/snaps/')):
                    self.log("Not Adding Device name : {0} used space in KB : {1} mount point : {2}".format(device,used,mountpoint))
                    total_used_gluster = total_used_gluster + int(used)
                else:
                    self.log("Adding Device name : {0} used space in KB : {1} mount point : {2}".format(device,used,mountpoint))
                    total_used = total_used + int(used) #return in KB

            if not len(network_fs_types) == 0:
                HandlerUtility.add_to_telemetery_data("networkFSTypeInDf",str(network_fs_types))
                HandlerUtility.add_to_telemetery_data("totalUsedNetworkShare",str(total_used_network_shares))
                self.log("Total used space in Bytes of network shares : {0}".format(total_used_network_shares * 1024))
            if total_used_gluster !=0 :
                HandlerUtility.add_to_telemetery_data("glusterFSSize",str(total_used_gluster))
            self.log("Total used space in Bytes : {0}".format(total_used * 1024))
            return total_used * 1024,False #Converting into Bytes
        except Exception as e:
            errMsg = 'Unable to fetch total used space with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg)
            return 0,True

    def get_storage_details(self,total_size,failure_flag):
        self.storageDetailsObj = Utils.Status.StorageDetails(self.partitioncount, total_size, False, failure_flag)

        self.log("partition count : {0}, total used size : {1}, is storage space present : {2}, is size computation failed : {3}".format(self.storageDetailsObj.partitionCount, self.storageDetailsObj.totalUsedSizeInBytes, self.storageDetailsObj.isStoragespacePresent, self.storageDetailsObj.isSizeComputationFailed))
        return self.storageDetailsObj

    def SetExtErrorCode(self, extErrorCode):
        if self.ExtErrorCode == ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.success : 
            self.ExtErrorCode = extErrorCode

    def SetSnapshotConsistencyType(self, snapshotConsistency):
        self.SnapshotConsistency = snapshotConsistency

    def SetHealthStatusCode(self, healthStatusCode):
        self.HealthStatusCode = healthStatusCode

    def do_status_json(self, operation, status, sub_status, status_code, message, telemetrydata, taskId, commandStartTimeUTCTicks, snapshot_info, vm_health_obj,total_size,failure_flag):
        tstamp = time.strftime(DateTimeFormat, time.gmtime())
        formattedMessage = Utils.Status.FormattedMessage("en-US",message)
        stat_obj = Utils.Status.StatusObj(self._context._name, operation, status, sub_status, status_code, formattedMessage, telemetrydata, self.get_storage_details(total_size,failure_flag), self.get_machine_id(), taskId, commandStartTimeUTCTicks, snapshot_info, vm_health_obj)
        top_stat_obj = Utils.Status.TopLevelStatus(self._context._version, tstamp, stat_obj)

        return top_stat_obj

    def get_extension_version(self):
        try:
            cur_dir = os.getcwd()
            cur_extension = cur_dir.split("/")[-1]
            extension_version = cur_extension.split("-")[-1]
            return extension_version
        except Exception as e:
            errMsg = 'Failed to retrieve the Extension version with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg)
            extension_version="Unknown"
            return extension_version

    def get_wala_version(self):
        try:
            file_pointer = open('/var/log/waagent.log','r')
            waagent_version = ''
            for line in file_pointer:
                if 'Azure Linux Agent Version' in line:
                    waagent_version = line.split(':')[-1]
            if waagent_version[:-1]=="": #for removing the trailing '\n' character
                waagent_version = self.get_wala_version_from_command()
                return waagent_version
            else:
                waagent_version = waagent_version[:-1].split("-")[-1] #getting only version number
                return waagent_version
        except Exception as e:
            errMsg = 'Failed to retrieve the wala version with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg)
            waagent_version="Unknown"
            return waagent_version

    def get_wala_version_from_command(self):
        try:
            cur_dir = os.getcwd()
            os.chdir("..")
            p = subprocess.Popen(['/usr/sbin/waagent', '-version'], stdout=subprocess.PIPE)
            process_wait_time = 30
            while(process_wait_time > 0 and p.poll() is None):
                time.sleep(1)
                process_wait_time -= 1
            out = p.stdout.read()
            out = str(out)
            if "Goal state agent: " in out:
                 waagent_version = out.split("Goal state agent: ")[1].strip()
            else:
                out =  out.split(" ")
                waagent = out[0]
                waagent_version = waagent.split("-")[-1] #getting only version number

            os.chdir(cur_dir)
            return waagent_version
        except Exception as e:
            errMsg = 'Failed to retrieve the wala version with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg)
            os.chdir(cur_dir)
            waagent_version="Unknown"
            return waagent_version

    def get_dist_info(self):
        try:
            if 'FreeBSD' in platform.system():
                release = re.sub('\-.*\Z', '', str(platform.release()))
                return "FreeBSD",release
            if 'NS-BSD' in platform.system():
                release = re.sub('\-.*\Z', '', str(platform.release()))
                return "NS-BSD", release
            if 'linux_distribution' in dir(platform):
                distinfo = list(platform.linux_distribution(full_distribution_name=0))
                # remove trailing whitespace in distro name
                if(distinfo[0] == ''):
                    osfile= open("/etc/os-release", "r")
                    for line in osfile:
                        lists=str(line).split("=")
                        if(lists[0]== "NAME"):
                            distroname = lists[1].split("\"")
                        if(lists[0]=="VERSION"):
                            distroversion = lists[1].split("\"")
                    osfile.close()
                    return distroname[1]+"-"+distroversion[1],platform.release()
                distinfo[0] = distinfo[0].strip()
                return  distinfo[0]+"-"+distinfo[1],platform.release()
            else:
                distinfo = platform.dist()
                return  distinfo[0]+"-"+distinfo[1],platform.release()
        except Exception as e:
            errMsg = 'Failed to retrieve the distinfo with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg)
            return "Unkonwn","Unkonwn"

    def substat_new_entry(self,sub_status,code,name,status,formattedmessage):
        sub_status_obj = Utils.Status.SubstatusObj(code,name,status,formattedmessage)
        sub_status.append(sub_status_obj)
        return sub_status

    def timedelta_total_seconds(self, delta):
        if not hasattr(datetime.timedelta, 'total_seconds'):
            return delta.days * 86400 + delta.seconds
        else:
            return delta.total_seconds()

    @staticmethod
    def add_to_telemetery_data(key,value):
        HandlerUtility.telemetry_data[key]=value

    def add_telemetry_data(self):
        os_version,kernel_version = self.get_dist_info()
        workloads = self.get_workload_running()
        HandlerUtility.add_to_telemetery_data("guestAgentVersion",self.get_wala_version_from_command())
        HandlerUtility.add_to_telemetery_data("extensionVersion",self.get_extension_version())
        HandlerUtility.add_to_telemetery_data("osVersion",os_version)
        HandlerUtility.add_to_telemetery_data("kernelVersion",kernel_version)
        HandlerUtility.add_to_telemetery_data("workloads",str(workloads))
        HandlerUtility.add_to_telemetery_data("prePostEnabled", str(self.pre_post_enabled))
    
    def convert_telemetery_data_to_bcm_serializable_format(self):
        HandlerUtility.serializable_telemetry_data = []
        for k,v in HandlerUtility.telemetry_data.items():
            each_telemetry_data = {}
            each_telemetry_data["Value"] = v
            each_telemetry_data["Key"] = k
            HandlerUtility.serializable_telemetry_data.append(each_telemetry_data)
 
    def do_status_report(self, operation, status, status_code, message, taskId = None, commandStartTimeUTCTicks = None, snapshot_info = None,total_size = 0,failure_flag = True ):
        self.log("{0},{1},{2},{3}".format(operation, status, status_code, message))
        sub_stat = []
        stat_rept = []
        self.add_telemetry_data()
        snapshotTelemetry = ""

        if CommonVariables.snapshotCreator in HandlerUtility.telemetry_data.keys():
            snapshotTelemetry = "{0}{1}={2}, ".format(snapshotTelemetry , CommonVariables.snapshotCreator , HandlerUtility.telemetry_data[CommonVariables.snapshotCreator])
        if CommonVariables.hostStatusCodePreSnapshot in HandlerUtility.telemetry_data.keys():
            snapshotTelemetry = "{0}{1}={2}, ".format(snapshotTelemetry , CommonVariables.hostStatusCodePreSnapshot , HandlerUtility.telemetry_data[CommonVariables.hostStatusCodePreSnapshot])
        if CommonVariables.hostStatusCodeDoSnapshot in HandlerUtility.telemetry_data.keys():
            snapshotTelemetry = "{0}{1}={2}, ".format(snapshotTelemetry , CommonVariables.hostStatusCodeDoSnapshot , HandlerUtility.telemetry_data[CommonVariables.hostStatusCodeDoSnapshot])

        if CommonVariables.statusBlobUploadError in HandlerUtility.telemetry_data.keys():
            message = "{0} {1}={2}, ".format(message , CommonVariables.statusBlobUploadError , HandlerUtility.telemetry_data[CommonVariables.statusBlobUploadError])
        message = message + snapshotTelemetry

        vm_health_obj = Utils.Status.VmHealthInfoObj(ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.ExtensionErrorCodeDict[self.ExtErrorCode], int(self.ExtErrorCode))

        consistencyTypeStr = CommonVariables.consistency_crashConsistent
        if (self.SnapshotConsistency != Utils.Status.SnapshotConsistencyType.crashConsistent):
            if (status_code == CommonVariables.success_appconsistent):
                self.SnapshotConsistency = Utils.Status.SnapshotConsistencyType.applicationConsistent
                consistencyTypeStr = CommonVariables.consistency_applicationConsistent
            elif (status_code == CommonVariables.success):
                self.SnapshotConsistency = Utils.Status.SnapshotConsistencyType.fileSystemConsistent
                consistencyTypeStr = CommonVariables.consistency_fileSystemConsistent
            else:
                self.SnapshotConsistency = Utils.Status.SnapshotConsistencyType.none
                consistencyTypeStr = CommonVariables.consistency_none
        HandlerUtility.add_to_telemetery_data("consistencyType", consistencyTypeStr)

        extensionResponseObj = Utils.Status.ExtensionResponse(message, self.SnapshotConsistency, "")
        message = str(json.dumps(extensionResponseObj, cls = ComplexEncoder))

        self.convert_telemetery_data_to_bcm_serializable_format()
        stat_rept = self.do_status_json(operation, status, sub_stat, status_code, message, HandlerUtility.serializable_telemetry_data, taskId, commandStartTimeUTCTicks, snapshot_info, vm_health_obj, total_size,failure_flag)
        time_delta = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
        time_span = self.timedelta_total_seconds(time_delta) * 1000
        date_place_holder = 'e2794170-c93d-4178-a8da-9bc7fd91ecc0'
        stat_rept.timestampUTC = date_place_holder
        date_string = r'\/Date(' + str((int)(time_span)) + r')\/'
        stat_rept = "[" + json.dumps(stat_rept, cls = ComplexEncoder) + "]"
        stat_rept = stat_rept.replace(date_place_holder,date_string)
        
        # Add Status as sub-status for Status to be written on Status-File
        sub_stat = self.substat_new_entry(sub_stat,'0',stat_rept,'success',None)
        if self.get_public_settings()[CommonVariables.vmType].lower() == CommonVariables.VmTypeV2.lower() and CommonVariables.isTerminalStatus(status) :
            status = CommonVariables.status_success
        stat_rept_file = self.do_status_json(operation, status, sub_stat, status_code, message, None, taskId, commandStartTimeUTCTicks, None, None,total_size,failure_flag)
        stat_rept_file =  "[" + json.dumps(stat_rept_file, cls = ComplexEncoder) + "]"

        # rename all other status files, or the WALA would report the wrong
        # status file.
        # because the wala choose the status file with the highest sequence
        # number to report.
        return stat_rept, stat_rept_file

    def write_to_status_file(self, stat_rept_file):
        try:
            if self._context._status_file:
                with open(self._context._status_file,'w+') as f:
                    f.write(stat_rept_file)
        except Exception as e:
            errMsg = 'Status file creation failed with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.log(errMsg)

    def is_status_file_exists(self):
        try:
            if os.path.exists(self._context._status_file):
                return True
            else:
                return False
        except Exception as e:
            self.log("exception is getting status file" + traceback.format_exc())
            return False

    def backup_settings_status_file(self, _seq_no):
        self.log("current seq no is " + _seq_no)
        for subdir, dirs, files in os.walk(self._context._config_dir):
            for file in files:
                try:
                    if(file.endswith('.settings') and file != (_seq_no + ".settings")):
                        new_file_name = file.replace(".","_")
                        os.rename(join(self._context._config_dir,file), join(self._context._config_dir,new_file_name))
                except Exception as e:
                    self.log("failed to rename the status file.")

        for subdir, dirs, files in os.walk(self._context._status_dir):
            for file in files:
                try:
                    if(file.endswith('.status') and file != (_seq_no + ".status")):
                        new_file_name = file.replace(".","_")
                        os.rename(join(self._context._status_dir,file), join(self._context._status_dir, new_file_name))
                except Exception as e:
                    self.log("failed to rename the status file.")

    def do_exit(self, exit_code, operation,status,code,message):
        try:
            HandlerUtility.add_to_telemetery_data("extErrorCode", str(ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.ExtensionErrorCodeDict[self.ExtErrorCode]))
            self.do_status_report(operation, status,code,message)
        except Exception as e:
            self.log("Can't update status: " + str(e))
        sys.exit(exit_code)

    def get_handler_settings(self):
        return self._context._config['runtimeSettings'][0]['handlerSettings']

    def get_protected_settings(self):
        return self.get_handler_settings().get('protectedSettings')

    def get_public_settings(self):
        return self.get_handler_settings().get('publicSettings')

    def is_prev_in_transition(self):
        curr_seq = self.get_last_seq()
        last_seq = curr_seq - 1
        if last_seq >= 0:
            self.log("previous status and path: " + str(last_seq) + "  " + str(self._context._status_dir))
            status_file_prev = os.path.join(self._context._status_dir, str(last_seq) + '_status')
            if os.path.isfile(status_file_prev) and os.access(status_file_prev, os.R_OK):
                searchfile = open(status_file_prev, "r")
                for line in searchfile:
                    if "Transition" in line: 
                        self.log("transitioning found in the previous status file")
                        searchfile.close()
                        return True
                searchfile.close()
        return False

    def get_prev_log(self):
        with open(self._context._log_file, "r") as f:
            lines = f.readlines()
        if(len(lines) > 300):
            lines = lines[-300:]
            return ''.join(str(x) for x in lines)
        else:
            return ''.join(str(x) for x in lines)
    
    def get_shell_script_log(self):
        lines = "" 
        try:
            with open(self._context._shell_log_file, "r") as f:
                lines = f.readlines()
            if(len(lines) > 10):
                lines = lines[-10:]
            return ''.join(str(x) for x in lines)
        except Exception as e:
            self.log("Can't receive shell log file: " + str(e))
            return lines

    def update_settings_file(self):
        if(self._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings') != None):
            del self._context._config['runtimeSettings'][0]['handlerSettings']['protectedSettings']
            self.log("removing the protected settings")
            waagent.SetFileContents(self._context._settings_file,json.dumps(self._context._config))

    def UriHasSpecialCharacters(self, blobs):
        uriHasSpecialCharacters = False

        if blobs is not None:
            for blob in blobs:
                blobUri = str(blob.split("?")[0])
                if '%' in blobUri:
                    self.log(blobUri + " URI has special characters")
                    uriHasSpecialCharacters = True

        return uriHasSpecialCharacters

    def get_workload_running(self):
        workloads = []
        try:
            dblist= ["mysqld","postgresql","oracle","cassandra",",mongo"] ## add all workload process name in lower case
            if os.path.isdir("/proc"):
                pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]
                for pid in pids:
                    pname = open(os.path.join('/proc', pid, 'cmdline'), 'rb').read()
                    for db in dblist :
                        if db in str(pname).lower() and db not in workloads :
                            self.log("workload running found with name : " + str(db))
                            workloads.append(db)
            return workloads
        except Exception as e:
            self.log("Unable to fetch running workloads" + str(e))
            return workloads
        
    def set_pre_post_enabled(self):
        self.pre_post_enabled = True
        
    @staticmethod
    def convert_to_string(txt):
        if sys.version_info > (3,):
            txt = str(txt, encoding='utf-8', errors="backslashreplace")
        else:
            txt = str(txt)
        return txt

class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj,'convertToDictionary'):
            return obj.convertToDictionary()
        else:
            return obj.__dict__

