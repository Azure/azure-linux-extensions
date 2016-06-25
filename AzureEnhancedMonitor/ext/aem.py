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

import os
import re
import socket
import traceback
import time
import datetime
import psutil
import urlparse
import xml.dom.minidom as minidom
from azure.storage import TableService, Entity
from Utils.WAAgentUtil import waagent, AddExtensionEvent


FAILED_TO_RETRIEVE_MDS_DATA="(03100)Failed to retrieve mds data"
FAILED_TO_RETRIEVE_LOCAL_DATA="(03101)Failed to retrieve local data"
FAILED_TO_RETRIEVE_STORAGE_DATA="(03102)Failed to retrieve storage data"
FAILED_TO_SERIALIZE_PERF_COUNTERS="(03103)Failed to serialize perf counters"

def timedelta_total_seconds(delta):

    if not hasattr(datetime.timedelta, 'total_seconds'):
        return delta.days * 86400 + delta.seconds
    else:
        return delta.total_seconds()

def get_host_base_from_uri(blob_uri):
    uri = urlparse.urlparse(blob_uri)
    netloc = uri.netloc
    if netloc is None:
        return None
    return netloc[netloc.find('.'):]

MonitoringIntervalInMinute = 1 #One minute
MonitoringInterval = 60 * MonitoringIntervalInMinute

#It takes sometime before the performance date reaches azure table.
AzureTableDelayInMinute = 5 #Five minute
AzureTableDelay = 60 * AzureTableDelayInMinute

AzureEnhancedMonitorVersion = "2.0.0"
LibDir = "/var/lib/AzureEnhancedMonitor"

LatestErrorRecord = "LatestErrorRecord"

def clearLastErrorRecord():
    errFile = os.path.join(LibDir, LatestErrorRecord)
    if os.path.exists(errFile) and os.path.isfile(errFile):
        os.remove(errFile)

def getLatestErrorRecord():
    errFile=os.path.join(LibDir, LatestErrorRecord)
    if os.path.exists(errFile) and os.path.isfile(errFile):
        with open(errFile, 'r') as f:
            return f.read()

    return "0"

def updateLatestErrorRecord(s):
    errFile = os.path.join(LibDir, LatestErrorRecord)
    maxRetry = 3
    for i in range(0, maxRetry):
        try:
            with open(errFile, "w+") as F:
                F.write(s.encode("utf8"))
                return
        except IOError:
            time.sleep(1)

    waagent.Error(("Failed to serialize latest error record to file:"
                    "{0}").format(errFile))
    AddExtensionEvent(message="failed to write latest error record")
    raise

def easyHash(s):
    """
    MDSD used the following hash algorithm to cal a first part of partition key
    """
    strHash = 0
    multiplier = 37
    for c in s:
        strHash = strHash * multiplier + ord(c)
        #Only keep the last 64bit, since the mod base is 100
        strHash = strHash % (1<<64) 
    return strHash % 100 #Assume eventVolume is Large

Epoch = datetime.datetime(1, 1, 1)
tickInOneSecond = 1000 * 10000 # 1s = 1000 * 10000 ticks

def getMDSTimestamp(unixTimestamp):
    unixTime = datetime.datetime.utcfromtimestamp(unixTimestamp)
    startTimestamp = int(timedelta_total_seconds(unixTime - Epoch))
    return startTimestamp * tickInOneSecond

def getIdentity():
    identity = socket.gethostname()
    return identity

def getMDSPartitionKey(identity, timestamp):
    hashVal = easyHash(identity)
    return "{0:0>19d}___{1:0>19d}".format(hashVal, timestamp)

def getAzureDiagnosticKeyRange():
    #Round down by MonitoringInterval
    endTime = (int(time.time()) / MonitoringInterval) * MonitoringInterval
    endTime = endTime - AzureTableDelay
    startTime = endTime - MonitoringInterval

    identity = getIdentity()
    startKey = getMDSPartitionKey(identity, getMDSTimestamp(startTime))
    endKey = getMDSPartitionKey(identity, getMDSTimestamp(endTime))
    return startKey, endKey

def getAzureDiagnosticCPUData(accountName, accountKey, hostBase,
                              startKey, endKey, deploymentId):
    try:
        waagent.Log("Retrieve diagnostic data(CPU).")
        table = "LinuxCpuVer2v0"
        tableService = TableService(account_name = accountName, 
                                    account_key = accountKey,
                                    host_base = hostBase)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}' "
                   "and DeploymentId eq '{2}'").format(startKey, endKey, deploymentId)
        oselect = ("PercentProcessorTime,DeploymentId")
        data = tableService.query_entities(table, ofilter, oselect, 1)
        if data is None or len(data) == 0:
            return None
        cpuPercent = float(data[0].PercentProcessorTime)
        return cpuPercent
    except Exception as e:
        waagent.Error((u"Failed to retrieve diagnostic data(CPU): {0} {1}"
                       "").format(e, traceback.format_exc()))
        updateLatestErrorRecord(FAILED_TO_RETRIEVE_MDS_DATA)
        AddExtensionEvent(message=FAILED_TO_RETRIEVE_MDS_DATA)
        return None
    

def getAzureDiagnosticMemoryData(accountName, accountKey, hostBase,
                                 startKey, endKey, deploymentId):
    try:
        waagent.Log("Retrieve diagnostic data: Memory")
        table = "LinuxMemoryVer2v0"
        tableService = TableService(account_name = accountName, 
                                    account_key = accountKey,
                                    host_base = hostBase)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}' "
                   "and DeploymentId eq '{2}'").format(startKey, endKey, deploymentId)
        oselect = ("PercentAvailableMemory,DeploymentId")
        data = tableService.query_entities(table, ofilter, oselect, 1)
        if data is None or len(data) == 0:
            return None
        memoryPercent = 100 - float(data[0].PercentAvailableMemory)
        return memoryPercent
    except Exception as e:
        waagent.Error((u"Failed to retrieve diagnostic data(Memory): {0} {1}"
                       "").format(e, traceback.format_exc()))
        updateLatestErrorRecord(FAILED_TO_RETRIEVE_MDS_DATA)
        AddExtensionEvent(message=FAILED_TO_RETRIEVE_MDS_DATA)
        return None

class AzureDiagnosticData(object):
    def __init__(self, config):
        self.config = config
        accountName = config.getLADName()
        accountKey = config.getLADKey()
        hostBase = config.getLADHostBase()
        hostname = socket.gethostname()
        deploymentId = config.getVmDeploymentId()
        startKey, endKey = getAzureDiagnosticKeyRange()
        self.cpuPercent = getAzureDiagnosticCPUData(accountName, 
                                                    accountKey,
                                                    hostBase,
                                                    startKey,
                                                    endKey,
                                                    deploymentId)
        self.memoryPercent = getAzureDiagnosticMemoryData(accountName, 
                                                          accountKey,
                                                          hostBase,
                                                          startKey,
                                                          endKey,
                                                          deploymentId)

    def getCPUPercent(self):
        return self.cpuPercent

    def getMemoryPercent(self):
        return self.memoryPercent

class AzureDiagnosticMetric(object):
    def __init__(self, config):
        self.config = config
        self.linux = LinuxMetric(self.config)
        self.azure = AzureDiagnosticData(self.config)
        self.timestamp = int(time.time()) - AzureTableDelay

    def getTimestamp(self):
        return self.timestamp

    def getCurrHwFrequency(self):
        return self.linux.getCurrHwFrequency()

    def getMaxHwFrequency(self):
        return self.linux.getMaxHwFrequency()

    def getCurrVMProcessingPower(self):
        return self.linux.getCurrVMProcessingPower()

    def getGuaranteedVMProcessingPower(self):
        return self.linux.getGuaranteedVMProcessingPower()

    def getMaxVMProcessingPower(self):
        return self.linux.getMaxVMProcessingPower()

    def getNumOfCoresPerCPU(self):
        return self.linux.getNumOfCoresPerCPU()

    def getNumOfThreadsPerCore(self):
        return self.linux.getNumOfThreadsPerCore()

    def getPhysProcessingPowerPerVCPU(self):
        return self.linux.getPhysProcessingPowerPerVCPU()

    def getProcessorType(self):
        return self.linux.getProcessorType()

    def getReferenceComputeUnit(self):
        return self.linux.getReferenceComputeUnit()

    def getVCPUMapping(self):
        return self.linux.getVCPUMapping()
    
    def getVMProcessingPowerConsumption(self):
        return self.azure.getCPUPercent()
    
    def getCurrMemAssigned(self):
        return self.linux.getCurrMemAssigned()
        
    def getGuaranteedMemAssigned(self):
        return self.linux.getGuaranteedMemAssigned()

    def getMaxMemAssigned(self):
        return self.linux.getMaxMemAssigned()

    def getVMMemConsumption(self):
        return self.azure.getMemoryPercent()

    def getNetworkAdapterIds(self):
        return self.linux.getNetworkAdapterIds()

    def getNetworkAdapterMapping(self, adapterId):
        return self.linux.getNetworkAdapterMapping(adapterId)

    def getMaxNetworkBandwidth(self, adapterId):
        return self.linux.getMaxNetworkBandwidth(adapterId)

    def getMinNetworkBandwidth(self, adapterId):
        return self.linux.getMinNetworkBandwidth(adapterId)

    def getNetworkReadBytes(self, adapterId):
        return self.linux.getNetworkReadBytes(adapterId)

    def getNetworkWriteBytes(self, adapterId):
        return self.linux.getNetworkWriteBytes(adapterId)

    def getNetworkPacketRetransmitted(self):
        return self.linux.getNetworkPacketRetransmitted()
  
    def getLastHardwareChange(self):
        return self.linux.getLastHardwareChange()

class CPUInfo(object):

    @staticmethod
    def getCPUInfo():
        cpuinfo = waagent.GetFileContents("/proc/cpuinfo")
        ret, lscpu = waagent.RunGetOutput("lscpu")
        return CPUInfo(cpuinfo, lscpu)

    def __init__(self, cpuinfo, lscpu):
        self.cpuinfo = cpuinfo
        self.lscpu = lscpu
        self.cores = 1;
        self.coresPerCpu = 1;
        self.threadsPerCore = 1;
        
        coresMatch = re.search("CPU(s):\s+(\d+)", self.lscpu)
        if coresMatch:
            self.cores = int(coresMatch.group(1))
        
        coresPerCpuMatch = re.search("Core(s) per socket:\s+(\d+)", self.lscpu)
        if coresPerCpuMatch:
            self.coresPerCpu = int(coresPerCpuMatch.group(1))
        
        threadsPerCoreMatch = re.search("Core(s) per socket:\s+(\d+)", self.lscpu)
        if threadsPerCoreMatch:
            self.threadsPerCore = int(threadsPerCoreMatch.group(1))
        
        model = re.search("model name\s+:\s+(.*)\s", self.cpuinfo)
        vendorId = re.search("vendor_id\s+:\s+(.*)\s", self.cpuinfo)
        if model and vendorId:
            self.processorType = "{0}, {1}".format(model.group(1), 
                                                   vendorId.group(1))
        else:
            self.processorType = None
        
        freqMatch = re.search("CPU MHz:\s+(.*)\s", self.lscpu)
        if freqMatch:
            self.frequency = float(freqMatch.group(1))
        else:
            self.frequency = None

        ht = re.match("flags\s.*\sht\s", self.cpuinfo)
        self.isHTon = ht is not None

    def getNumOfCoresPerCPU(self):
        return self.coresPerCpu
    
    def getNumOfCores(self):
        return self.cores

    def getNumOfThreadsPerCore(self):
        return self.threadsPerCore
    
    def getProcessorType(self):
        return self.processorType
   
    def getFrequency(self):
        return self.frequency

    def isHyperThreadingOn(self):
        return self.isHTon

    def getCPUPercent(self):
        return psutil.cpu_percent()
    
class MemoryInfo(object):
    def __init__(self):
        self.memInfo = psutil.virtual_memory()

    def getMemSize(self):
        return self.memInfo[0]  / 1024 / 1024 #MB

    def getMemPercent(self):
        return self.memInfo[2] #%

def getMacAddress(adapterId):
    nicAddrPath = os.path.join("/sys/class/net", adapterId, "address")
    mac = waagent.GetFileContents(nicAddrPath)
    mac = mac.strip()
    mac = mac.replace(":", "-")
    return mac

def sameList(l1, l2):
    if l1 is None or l2 is None:
        return l1 == l2
    if len(l1) != len(l2):
        return False
    for i in range(0, len(l1)):
        if l1[i] != l2[i]:
            return False
    return True

class NetworkInfo(object):
    def __init__(self):
        self.nics = psutil.net_io_counters(pernic=True)
        self.nicNames = []
        for nicName, stat in self.nics.iteritems():
            if nicName != 'lo':
                self.nicNames.append(nicName)

    def getAdapterIds(self):
        return self.nicNames

    def getNetworkReadBytes(self, adapterId):
        net = psutil.net_io_counters(pernic=True)
        if net[adapterId] != None:
            bytes_recv1 = net[adapterId][1]
            time1 = time.time()
            
            time.sleep(0.2)
            
            net = psutil.net_io_counters(pernic=True)
            bytes_recv2 = net[adapterId][1]
            time2 = time.time()
            
            interval = (time2 - time1)
            
            return (bytes_recv2 - bytes_recv1) / interval
        else:
            return 0

    def getNetworkWriteBytes(self, adapterId):
        net = psutil.net_io_counters(pernic=True)
        if net[adapterId] != None:
            bytes_sent1 = net[adapterId][0]
            time1 = time.time()
            
            time.sleep(0.2)
            
            net = psutil.net_io_counters(pernic=True)
            bytes_sent2 = net[adapterId][0]
            time2 = time.time()
            
            interval = (time2 - time1)
            
            return (bytes_sent2 - bytes_sent1) / interval
        else:
            return 0

    def getNetstat(self):
        retCode, output = waagent.RunGetOutput("netstat -s", chk_err=False)
        return output

    def getNetworkPacketRetransmitted(self):
        netstat = self.getNetstat()
        match = re.search("(\d+)\s*segments retransmited", netstat)
        if match != None:
            return int(match.group(1))
        else:
            waagent.Error("Failed to parse netstat output: {0}".format(netstat))
            updateLatestErrorRecord(FAILED_TO_RETRIEVE_LOCAL_DATA)
            AddExtensionEvent(message=FAILED_TO_RETRIEVE_LOCAL_DATA)
            return None


HwInfoFile = os.path.join(LibDir, "HwInfo")
class HardwareChangeInfo(object):
    def __init__(self, networkInfo):
        self.networkInfo = networkInfo

    def getHwInfo(self):
        if not os.path.isfile(HwInfoFile):
            return None, None
        hwInfo = waagent.GetFileContents(HwInfoFile).split("\n")
        return int(hwInfo[0]), hwInfo[1:]

    def setHwInfo(self, timestamp, hwInfo):
        content = str(timestamp)
        content = content + "\n" + "\n".join(hwInfo)
        waagent.SetFileContents(HwInfoFile, content)

    def getLastHardwareChange(self):
        oldTime, oldMacs = self.getHwInfo()
        newMacs = map(lambda x : getMacAddress(x), 
                      self.networkInfo.getAdapterIds())
        newTime = int(time.time())
        newMacs.sort()
        if oldMacs is None or not sameList(newMacs, oldMacs):
            #Hardware changed
            if newTime < oldTime:
                waagent.Warn(("Hardware change detected. But the old timestamp "
                               "is greater than now, {0}>{1}.").format(oldTime, 
                                                                       newTime))
            self.setHwInfo(newTime, newMacs)
            return newTime
        else:
            return oldTime

class LinuxMetric(object):
    def __init__(self, config):
        self.config = config
        #CPU
        self.cpuInfo = CPUInfo.getCPUInfo()
        #Memory
        self.memInfo = MemoryInfo()
        #Network
        self.networkInfo = NetworkInfo()
        #Detect hardware change
        self.hwChangeInfo = HardwareChangeInfo(self.networkInfo)
        self.timestamp = int(time.time())

    def getTimestamp(self):
        return self.timestamp

    def getCurrHwFrequency(self):
        return self.cpuInfo.getFrequency()

    def getMaxHwFrequency(self):
        return self.getCurrHwFrequency()

    def getCurrVMProcessingPower(self):
        if self.config.isCpuOverCommitted():
            return None
        else:
            return self.cpuInfo.getNumOfCores()

    def getGuaranteedVMProcessingPower(self):
        return self.getCurrVMProcessingPower()

    def getMaxVMProcessingPower(self):
        return self.getCurrVMProcessingPower()

    def getNumOfCoresPerCPU(self):
        return self.cpuInfo.getNumOfCoresPerCPU()

    def getNumOfThreadsPerCore(self):
        return self.cpuInfo.getNumOfThreadsPerCore()

    def getPhysProcessingPowerPerVCPU(self):
        return 1 / float(self.getNumOfThreadsPerCore())

    def getProcessorType(self):
        return self.cpuInfo.getProcessorType()

    def getReferenceComputeUnit(self):
        return self.getProcessorType()

    def getVCPUMapping(self):
        return "thread" if self.cpuInfo.isHyperThreadingOn() else "core"
    
    def getVMProcessingPowerConsumption(self):
        return self.memInfo.getMemPercent()
    
    def getCurrMemAssigned(self):
        if self.config.isMemoryOverCommitted():
            return None
        else:
            return self.memInfo.getMemSize()
        
    def getGuaranteedMemAssigned(self):
        return self.getCurrMemAssigned()

    def getMaxMemAssigned(self):
        return self.getCurrMemAssigned()

    def getVMMemConsumption(self):
        return self.memInfo.getMemPercent()

    def getNetworkAdapterIds(self):
        return self.networkInfo.getAdapterIds()

    def getNetworkAdapterMapping(self, adapterId):
        return getMacAddress(adapterId)

    def getMaxNetworkBandwidth(self, adapterId):
        return 1000 #Mbit/s 

    def getMinNetworkBandwidth(self, adapterId):
        return 1000 #Mbit/s 

    def getNetworkReadBytes(self, adapterId):
        return self.networkInfo.getNetworkReadBytes(adapterId)

    def getNetworkWriteBytes(self, adapterId):
        return self.networkInfo.getNetworkWriteBytes(adapterId)

    def getNetworkPacketRetransmitted(self):
        return self.networkInfo.getNetworkPacketRetransmitted()
  
    def getLastHardwareChange(self):
        return self.hwChangeInfo.getLastHardwareChange()

class VMDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = []
        if self.config.isLADEnabled():
            metrics = AzureDiagnosticMetric(self.config)
        else:
            metrics = LinuxMetric(self.config)

        #CPU
        counters.append(self.createCounterCurrHwFrequency(metrics))
        counters.append(self.createCounterMaxHwFrequency(metrics))
        counters.append(self.createCounterCurrVMProcessingPower(metrics))
        counters.append(self.createCounterGuaranteedVMProcessingPower(metrics))
        counters.append(self.createCounterMaxVMProcessingPower(metrics))
        counters.append(self.createCounterNumOfCoresPerCPU(metrics))
        counters.append(self.createCounterNumOfThreadsPerCore(metrics))
        counters.append(self.createCounterPhysProcessingPowerPerVCPU(metrics))
        counters.append(self.createCounterProcessorType(metrics))
        counters.append(self.createCounterReferenceComputeUnit(metrics))
        counters.append(self.createCounterVCPUMapping(metrics))
        counters.append(self.createCounterVMProcessingPowerConsumption(metrics))

        #Memory
        counters.append(self.createCounterCurrMemAssigned(metrics))
        counters.append(self.createCounterGuaranteedMemAssigned(metrics))
        counters.append(self.createCounterMaxMemAssigned(metrics))
        counters.append(self.createCounterVMMemConsumption(metrics))

        #Network
        adapterIds = metrics.getNetworkAdapterIds()
        for adapterId in adapterIds:
            if adapterId.startswith('eth'):
                counters.append(self.createCounterAdapterId(adapterId))
                counters.append(self.createCounterNetworkMapping(metrics, adapterId))
                counters.append(self.createCounterMinNetworkBandwidth(metrics, adapterId))
                counters.append(self.createCounterMaxNetworkBandwidth(metrics, adapterId))
                counters.append(self.createCounterNetworkReadBytes(metrics, adapterId))
                counters.append(self.createCounterNetworkWriteBytes(metrics, adapterId))
        counters.append(self.createCounterNetworkPacketRetransmitted(metrics))
        
        #Hardware change
        counters.append(self.createCounterLastHardwareChange(metrics))

        #Error
        counters.append(self.createCounterError())

        return counters
    
    def createCounterLastHardwareChange(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "config",
                           name = "Last Hardware Change",
                           value = metrics.getLastHardwareChange(),
                           unit="posixtime")

    def createCounterError(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "config",
                           name = "Error",
                           value = getLatestErrorRecord())

    def createCounterCurrHwFrequency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "cpu",
                           name = "Current Hw Frequency",
                           value = metrics.getCurrHwFrequency(),
                           unit = "MHz",
                           refreshInterval = 60)

    def createCounterMaxHwFrequency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "cpu",
                           name = "Max Hw Frequency",
                           value = metrics.getMaxHwFrequency(),
                           unit = "MHz")

    def createCounterCurrVMProcessingPower(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Current VM Processing Power",
                           value = metrics.getCurrVMProcessingPower(),
                           unit = "compute unit")

    def createCounterMaxVMProcessingPower(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Max. VM Processing Power",
                           value = metrics.getMaxVMProcessingPower(),
                           unit = "compute unit")

    def createCounterGuaranteedVMProcessingPower(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Guaranteed VM Processing Power",
                           value = metrics.getGuaranteedVMProcessingPower(),
                           unit = "compute unit")

    def createCounterNumOfCoresPerCPU(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Number of Cores per CPU",
                           value = metrics.getNumOfCoresPerCPU())

    def createCounterNumOfThreadsPerCore(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Number of Threads per Core",
                           value = metrics.getNumOfThreadsPerCore())

    def createCounterPhysProcessingPowerPerVCPU(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "cpu",
                           name = "Phys. Processing Power per vCPU",
                           value = metrics.getPhysProcessingPowerPerVCPU())

    def createCounterProcessorType(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "cpu",
                           name = "Processor Type",
                           value = metrics.getProcessorType())

    def createCounterReferenceComputeUnit(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "cpu",
                           name = "Reference Compute Unit",
                           value = metrics.getReferenceComputeUnit())

    def createCounterVCPUMapping(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "cpu",
                           name = "vCPU Mapping",
                           value = metrics.getVCPUMapping())

    def createCounterVMProcessingPowerConsumption(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "cpu",
                           name = "VM Processing Power Consumption",
                           value = metrics.getVMProcessingPowerConsumption(),
                           unit = "%",
                           timestamp = metrics.getTimestamp(),
                           refreshInterval = 60)

    def createCounterCurrMemAssigned(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "memory",
                           name = "Current Memory assigned",
                           value = metrics.getCurrMemAssigned(),
                           unit = "MB")

    def createCounterMaxMemAssigned(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "memory",
                           name = "Max Memory assigned",
                           value = metrics.getMaxMemAssigned(),
                           unit = "MB")

    def createCounterGuaranteedMemAssigned(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "memory",
                           name = "Guaranteed Memory assigned",
                           value = metrics.getGuaranteedMemAssigned(),
                           unit = "MB")

    def createCounterVMMemConsumption(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "memory",
                           name = "VM Memory Consumption",
                           value = metrics.getVMMemConsumption(),
                           unit = "%",
                           timestamp = metrics.getTimestamp(),
                           refreshInterval = 60)

    def createCounterAdapterId(self, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "network",
                           name = "Adapter Id",
                           instance = adapterId,
                           value = adapterId)

    def createCounterNetworkMapping(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "network",
                           name = "Mapping",
                           instance = adapterId,
                           value = metrics.getNetworkAdapterMapping(adapterId))

    def createCounterMaxNetworkBandwidth(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "VM Maximum Network Bandwidth",
                           instance = adapterId,
                           value = metrics.getMaxNetworkBandwidth(adapterId),
                           unit = "Mbit/s")

    def createCounterMinNetworkBandwidth(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "VM Minimum Network Bandwidth",
                           instance = adapterId,
                           value = metrics.getMinNetworkBandwidth(adapterId),
                           unit = "Mbit/s")

    def createCounterNetworkReadBytes(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "network",
                           name = "Network Read Bytes",
                           instance = adapterId,
                           value = metrics.getNetworkReadBytes(adapterId),
                           unit = "byte/s")

    def createCounterNetworkWriteBytes(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "network",
                           name = "Network Write Bytes",
                           instance = adapterId,
                           value = metrics.getNetworkWriteBytes(adapterId),
                           unit = "byte/s")

    def createCounterNetworkPacketRetransmitted(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Packets Retransmitted",
                           value = metrics.getNetworkPacketRetransmitted(),
                           unit = "packets/min")

def getStorageTimestamp(unixTimestamp):
    tformat = "{0:0>4d}{1:0>2d}{2:0>2d}T{3:0>2d}{4:0>2d}"
    ts = time.gmtime(unixTimestamp)
    return tformat.format(ts.tm_year,
                          ts.tm_mon,
                          ts.tm_mday,
                          ts.tm_hour,
                          ts.tm_min)
    

def getStorageTableKeyRange():
    #Round down by MonitoringInterval
    endTime = int(time.time()) / MonitoringInterval * MonitoringInterval 
    endTime = endTime - AzureTableDelay
    startTime = endTime - MonitoringInterval
    return getStorageTimestamp(startTime), getStorageTimestamp(endTime)

def getStorageMetrics(account, key, hostBase, table, startKey, endKey):
    try:
        waagent.Log("Retrieve storage metrics data.")
        tableService = TableService(account_name = account, 
                                    account_key = key,
                                    host_base = hostBase)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}'"
                   "").format(startKey, endKey)
        oselect = ("TotalRequests,TotalIngress,TotalEgress,AverageE2ELatency,"
                   "AverageServerLatency,RowKey")
        metrics = tableService.query_entities(table, ofilter, oselect)
        waagent.Log("{0} records returned.".format(len(metrics)))
        return metrics
    except Exception as e:
        waagent.Error((u"Failed to retrieve storage metrics data: {0} {1}"
                       "").format(e, traceback.format_exc()))
        updateLatestErrorRecord(FAILED_TO_RETRIEVE_STORAGE_DATA)
        AddExtensionEvent(message=FAILED_TO_RETRIEVE_STORAGE_DATA)
        return None

def getDataDisks():
    blockDevs = os.listdir('/sys/block')
    dataDisks = filter(lambda d : re.match("sd[c-z]", d), blockDevs)
    return dataDisks

def getFirstLun(dev):
    path = os.path.join("/sys/block", dev, "device/scsi_disk")
    for lun in os.listdir(path):
        return int(lun[-1])

class DiskInfo(object):
    def __init__(self, config):
        self.config = config

    def getDiskMapping(self):
        osdiskVhd = "{0} {1}".format(self.config.getOSDiskAccount(),
                                     self.config.getOSDiskName())
        osdisk = {
                "vhd":osdiskVhd, 
                "type": self.config.getOSDiskType(),
                "caching": self.config.getOSDiskCaching(),
                "iops": self.config.getOSDiskSLAIOPS(),
                "throughput": self.config.getOSDiskSLAThroughput(),
        }

        diskMapping = {
                "/dev/sda": osdisk,
        }

        dataDisks = getDataDisks()
        if dataDisks is None or len(dataDisks) == 0:
            return diskMapping
        
        lunToDevMap = {}
        for dev in dataDisks:
            lun = getFirstLun(dev)
            lunToDevMap[lun] = dev

        diskCount = self.config.getDataDiskCount()
        for i in range(0, diskCount):
            lun = self.config.getDataDiskLun(i)
            datadiskVhd = "{0} {1}".format(self.config.getDataDiskAccount(i),
                                           self.config.getDataDiskName(i))
            datadisk = {
                    "vhd": datadiskVhd,
                    "type": self.config.getDataDiskType(i),
                    "caching": self.config.getDataDiskCaching(i),
                    "iops": self.config.getDataDiskSLAIOPS(i),
                    "throughput": self.config.getDataDiskSLAThroughput(i),
            }
            if lun in lunToDevMap:
                dev = lunToDevMap[lun]
                diskMapping[dev] = datadisk
            else:
                waagent.Warn("Couldn't find disk with lun: {0}".format(lun))

        return diskMapping 

def isUserRead(op):
    if not op.startswith("user;"):
        return False
    op = op[5:]
    for prefix in ["Get", "List", "Preflight"]:
        if op.startswith(prefix):
            return True
    return False

def isUserWrite(op):
    if not op.startswith("user;"):
        return False
    op = op[5:]
    for prefix in ["Put" ,"Set" ,"Clear" ,"Delete" ,"Create" ,"Snapshot"]:    
        if op.startswith(prefix):
            return True
    return False

def storageStat(metrics, opFilter):
    stat = {}
    stat['bytes'] = None
    stat['ops'] = None
    stat['e2eLatency'] = None
    stat['serverLatency'] = None
    stat['throughput'] = None
    if metrics is None:
        return stat

    metrics = filter(lambda x : opFilter(x.RowKey), metrics)
    stat['bytes'] = sum(map(lambda x : x.TotalIngress + x.TotalEgress, 
                            metrics))
    stat['ops'] = sum(map(lambda x : x.TotalRequests, metrics))
    if stat['ops'] != 0:
        stat['e2eLatency'] = sum(map(lambda x : x.TotalRequests * \
                                                x.AverageE2ELatency, 
                                     metrics)) / stat['ops']
        stat['serverLatency'] = sum(map(lambda x : x.TotalRequests * \
                                                   x.AverageServerLatency, 
                                        metrics)) / stat['ops']
    #Convert to MB/s
    stat['throughput'] = float(stat['bytes']) / (1024 * 1024) / 60 
    return stat

class AzureStorageStat(object):

    def __init__(self, metrics):
        self.metrics = metrics
        self.rStat = storageStat(metrics, isUserRead)
        self.wStat = storageStat(metrics, isUserWrite)

    def getReadBytes(self):
        return self.rStat['bytes']

    def getReadOps(self):
        return self.rStat['ops']

    def getReadOpE2ELatency(self):
        return self.rStat['e2eLatency']

    def getReadOpServerLatency(self):
        return self.rStat['serverLatency']

    def getReadOpThroughput(self):
        return self.rStat['throughput']

    def getWriteBytes(self):
        return self.wStat['bytes']

    def getWriteOps(self):
        return self.wStat['ops']

    def getWriteOpE2ELatency(self):
        return self.wStat['e2eLatency']

    def getWriteOpServerLatency(self):
        return self.wStat['serverLatency']

    def getWriteOpThroughput(self):
        return self.wStat['throughput']


class StorageDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = []

        #Add disk mapping for resource disk
        counters.append(self.createCounterDiskMapping("/dev/sdb", 
                                                      "not mapped to vhd"))
        #Add disk mapping for osdisk and data disk
        diskMapping = DiskInfo(self.config).getDiskMapping()
        for dev, disk in diskMapping.iteritems():
            counters.append(self.createCounterDiskMapping(dev, disk.get("vhd")))
            counters.append(self.createCounterDiskType(dev, disk.get("type")))
            counters.append(self.createCounterDiskCaching(dev, disk.get("caching")))
            if disk.get("type") == "Premium":
                counters.append(self.createCounterDiskIOPS(dev, disk.get("iops")))
                counters.append(self.createCounterDiskThroughput(dev, disk.get("throughput")))

        accounts = self.config.getStorageAccountNames()
        for account in accounts:
            if self.config.getStorageAccountType(account) == "Standard":
                counters.extend(self.collectMetrixForStandardStorage(account))
        return counters

    def collectMetrixForStandardStorage(self, account):
        counters = []
        startKey, endKey = getStorageTableKeyRange()
        tableName = self.config.getStorageAccountMinuteTable(account)
        accountKey = self.config.getStorageAccountKey(account)
        hostBase = self.config.getStorageHostBase(account)
        metrics = getStorageMetrics(account, 
                                    accountKey,
                                    hostBase,
                                    tableName,
                                    startKey,
                                    endKey)
        stat = AzureStorageStat(metrics)
        counters.append(self.createCounterStorageId(account))
        counters.append(self.createCounterReadBytes(account, stat))
        counters.append(self.createCounterReadOps(account, stat))
        counters.append(self.createCounterReadOpE2ELatency(account, stat))
        counters.append(self.createCounterReadOpServerLatency(account, stat))
        counters.append(self.createCounterReadOpThroughput(account, stat))
        counters.append(self.createCounterWriteBytes(account, stat))
        counters.append(self.createCounterWriteOps(account, stat))
        counters.append(self.createCounterWriteOpE2ELatency(account, stat))
        counters.append(self.createCounterWriteOpServerLatency(account, stat))
        counters.append(self.createCounterWriteOpThroughput(account, stat))
        return counters

    def createCounterDiskType(self, dev, diskType):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "disk",
                           name = "Storage Type",
                           instance = dev,
                           value = diskType)

    def createCounterDiskCaching(self, dev, caching):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "disk",
                           name = "Caching",
                           instance = dev,
                           value = caching)

    def createCounterDiskThroughput(self, dev, throughput):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "disk",
                           name = "SLA Throughput",
                           instance = dev,
                           unit = "MB/sec",
                           value = throughput)

    def createCounterDiskIOPS(self, dev, iops):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "disk",
                           name = "SLA",
                           instance = dev,
                           unit = "Ops/sec",
                           value = iops)

    def createCounterReadBytes(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "storage",
                           name = "Storage Read Bytes",
                           instance = account,
                           value = stat.getReadBytes(),
                           unit = 'byte',
                           refreshInterval = 60)

    def createCounterReadOps(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "storage",
                           name = "Storage Read Ops",
                           instance = account,
                           value = stat.getReadOps(),
                           refreshInterval = 60)

    def createCounterReadOpE2ELatency(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Op Latency E2E msec",
                           instance = account,
                           value = stat.getReadOpE2ELatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterReadOpServerLatency(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Op Latency Server msec",
                           instance = account,
                           value = stat.getReadOpServerLatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterReadOpThroughput(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Throughput E2E MB/sec",
                           instance = account,
                           value = stat.getReadOpThroughput(),
                           unit = 'MB/s',
                           refreshInterval = 60)

    def createCounterWriteBytes(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "storage",
                           name = "Storage Write Bytes",
                           instance = account,
                           value = stat.getWriteBytes(),
                           unit = 'byte',
                           refreshInterval = 60)

    def createCounterWriteOps(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "storage",
                           name = "Storage Write Ops",
                           instance = account,
                           value = stat.getWriteOps(),
                           refreshInterval = 60)

    def createCounterWriteOpE2ELatency(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Op Latency E2E msec",
                           instance = account,
                           value = stat.getWriteOpE2ELatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterWriteOpServerLatency(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Op Latency Server msec",
                           instance = account,
                           value = stat.getWriteOpServerLatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterWriteOpThroughput(self, account, stat):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Throughput E2E MB/sec",
                           instance = account,
                           value = stat.getWriteOpThroughput(),
                           unit = 'MB/s',
                           refreshInterval = 60)


    def createCounterStorageId(self, account):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "storage",
                           name = "Storage ID",
                           instance = account,
                           value = account)

    def createCounterDiskMapping(self, dev, vhd):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "storage",
                           name = "Phys. Disc to Storage Mapping",
                           instance = dev,
                           value = vhd)
                   
class HvInfo(object):
    def __init__(self):
        self.hvName = None;
        self.hvVersion = None;
        root_dir = os.path.dirname(__file__)
        cmd = os.path.join(root_dir, "bin/hvinfo")
        ret, output = waagent.RunGetOutput(cmd, chk_err=False)
        print(ret)
        if ret ==0 and output is not None:
            lines = output.split("\n")
            if len(lines) >= 2:
                self.hvName = lines[0]
                self.hvVersion = lines[1]

    def getHvName(self):
        return self.hvName

    def getHvVersion(self):
        return self.hvVersion

class StaticDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = []
        hvInfo = HvInfo()
        counters.append(self.createCounterCloudProvider())
        counters.append(self.createCounterCpuOverCommitted())
        counters.append(self.createCounterMemoryOverCommitted())
        counters.append(self.createCounterDataProviderVersion())
        counters.append(self.createCounterDataSources())
        counters.append(self.createCounterInstanceType())
        counters.append(self.createCounterVirtSln(hvInfo.getHvName()))
        counters.append(self.createCounterVirtSlnVersion(hvInfo.getHvVersion()))
        vmSLAThroughput = self.config.getVMSLAThroughput()
        if vmSLAThroughput is not None:
            counters.append(self.createCounterVMSLAThroughput(vmSLAThroughput))
        vmSLAIOPS = self.config.getVMSLAIOPS()
        if vmSLAIOPS is not None:
            counters.append(self.createCounterVMSLAIOPS(vmSLAIOPS))

        return counters
    
    def createCounterVMSLAThroughput(self, throughput):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "config",
                           name = "SLA Max Disk Bandwidth per VM",
                           unit = "Ops/sec",
                           value = throughput)
     
    def createCounterVMSLAIOPS(self, iops):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "config",
                           name = "SLA Max Disk IOPS per VM",
                           unit = "Ops/sec",
                           value = iops)

    def createCounterCloudProvider(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Cloud Provider",
                           value = "Microsoft Azure")

    def createCounterVirtSlnVersion(self, hvVersion):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Virtualization Solution Version",
                           value = hvVersion)

    def createCounterVirtSln(self, hvName):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Virtualization Solution",
                           value = hvName)
  
    def createCounterInstanceType(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Instance Type",
                           value = self.config.getVmSize())

    def createCounterDataSources(self):
        dataSource = "wad" if self.config.isLADEnabled() else "local"
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Data Sources",
                           value = dataSource)

    def createCounterDataProviderVersion(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Data Provider Version",
                           value = AzureEnhancedMonitorVersion)

    def createCounterMemoryOverCommitted(self):
        value = "yes" if self.config.isMemoryOverCommitted() else "no"
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Memory Over-Provisioning",
                           value = value)

    def createCounterCpuOverCommitted(self):
        value = "yes" if self.config.isCpuOverCommitted() else "no"
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "CPU Over-Provisioning",
                           value = value)

class PerfCounterType(object):
    COUNTER_TYPE_INVALID = 0
    COUNTER_TYPE_INT = 1
    COUNTER_TYPE_DOUBLE = 2
    COUNTER_TYPE_LARGE = 3
    COUNTER_TYPE_STRING = 4

class PerfCounter(object):
    def __init__(self, 
                 counterType, 
                 category, 
                 name, 
                 value, 
                 instance="",
                 unit="none",
                 timestamp = None,
                 refreshInterval=0):
        self.counterType = counterType
        self.category = category
        self.name = name
        self.instance = instance
        self.value = value
        self.unit = unit
        self.refreshInterval = refreshInterval
        if(timestamp):
            self.timestamp = timestamp
        else:
            self.timestamp = int(time.time())
        self.machine = socket.gethostname()

    def __str__(self):
        return (u"{0};{1};{2};{3};{4};{5};{6};{7};{8};{9};\n"
                 "").format(self.counterType,
                            self.category,
                            self.name,
                            self.instance,
                            0 if self.value is not None else 1,
                            self.value if self.value is not None else "",
                            self.unit,
                            self.refreshInterval,
                            self.timestamp,
                            self.machine)

    __repr__ = __str__

class EnhancedMonitor(object):
    def __init__(self, config):
        self.dataSources = []
        self.dataSources.append(VMDataSource(config))
        self.dataSources.append(StorageDataSource(config))
        self.dataSources.append(StaticDataSource(config))
        self.writer = PerfCounterWriter()

    def run(self):
        counters = []
        for dataSource in self.dataSources:
            counters.extend(dataSource.collect())
        clearLastErrorRecord()
        self.writer.write(counters)

EventFile=os.path.join(LibDir, "PerfCounters")
class PerfCounterWriter(object):
    def write(self, counters, maxRetry = 3, eventFile=EventFile):
        for i in range(0, maxRetry):
            try:
                self._write(counters, eventFile)
                waagent.Log(("Write {0} counters to event file."
                             "").format(len(counters)))
                return
            except IOError as e:
                waagent.Warn((u"Write to perf counters file failed: {0}"
                              "").format(e))
                waagent.Log("Retry: {0}".format(i))
                time.sleep(1)

        waagent.Error(("Failed to serialize perf counter to file:"
                       "{0}").format(eventFile))
        updateLatestErrorRecord(FAILED_TO_SERIALIZE_PERF_COUNTERS)
        AddExtensionEvent(message=FAILED_TO_SERIALIZE_PERF_COUNTERS)
        raise

    def _write(self, counters, eventFile):
        with open(eventFile, "w+") as F:
            F.write("".join(map(lambda c : str(c), counters)).encode("utf8"))

class EnhancedMonitorConfig(object):
    def __init__(self, publicConfig, privateConfig):
        xmldoc = minidom.parse('/var/lib/waagent/SharedConfig.xml')
        self.deployment = xmldoc.getElementsByTagName('Deployment')
        self.role = xmldoc.getElementsByTagName('Role')
        self.configData = {}
        diskCount = 0
        accountNames = []
        for item in publicConfig["cfg"]:
            self.configData[item["key"]] = item["value"]
            if item["key"].startswith("disk.lun"):
                diskCount = diskCount + 1
            if item["key"].endswith("minute.name"):
                accountNames.append(item["value"])

        for item in privateConfig["cfg"]:
            self.configData[item["key"]] = item["value"]

        self.configData["disk.count"] = diskCount
        self.configData["account.names"] = accountNames


    def getVmSize(self):
        return self.configData.get("vmsize")

    def getVmRoleInstance(self):
        return self.role[0].attributes['name'].value

    def getVmDeploymentId(self):
        return self.deployment[0].attributes['name'].value

    def isMemoryOverCommitted(self):
        return self.configData.get("vm.memory.isovercommitted")

    def isCpuOverCommitted(self):
        return self.configData.get("vm.cpu.isovercommitted")

    def getScriptVersion(self):
        return self.configData.get("script.version")

    def isVerbose(self):
        flag = self.configData.get("verbose")
        return flag == "1" or flag == 1

    def getVMSLAIOPS(self):
        return self.configData.get("vm.sla.iops")

    def getVMSLAThroughput(self):
        return self.configData.get("vm.sla.throughput")

    def getOSDiskName(self):
        return self.configData.get("osdisk.name")

    def getOSDiskAccount(self):
        osdiskConnMinute = self.getOSDiskConnMinute()
        return self.configData.get("{0}.name".format(osdiskConnMinute))

    def getOSDiskConnMinute(self):
        return self.configData.get("osdisk.connminute")

    def getOSDiskConnHour(self):
        return self.configData.get("osdisk.connhour")

    def getOSDiskType(self):
        return self.configData.get("osdisk.type")

    def getOSDiskCaching(self):
        return self.configData.get("osdisk.caching")

    def getOSDiskSLAIOPS(self):
        return self.configData.get("osdisk.sla.iops")
    
    def getOSDiskSLAThroughput(self):
        return self.configData.get("osdisk.sla.throughput")
    
    def getDataDiskCount(self):
        return self.configData.get("disk.count")

    def getDataDiskLun(self, index):
        return self.configData.get("disk.lun.{0}".format(index))

    def getDataDiskName(self, index):
        return self.configData.get("disk.name.{0}".format(index))

    def getDataDiskAccount(self, index):
        return self.configData.get("disk.account.{0}".format(index))

    def getDataDiskConnMinute(self, index):
        return self.configData.get("disk.connminute.{0}".format(index))

    def getDataDiskConnHour(self, index):
        return self.configData.get("disk.connhour.{0}".format(index))
    
    def getDataDiskType(self, index):
        return self.configData.get("disk.type.{0}".format(index))

    def getDataDiskCaching(self, index):
        return self.configData.get("disk.caching.{0}".format(index))

    def getDataDiskSLAIOPS(self, index):
        return self.configData.get("disk.sla.iops.{0}".format(index))
    
    def getDataDiskSLAThroughput(self, index):
        return self.configData.get("disk.sla.throughput.{0}".format(index))
    
    def getStorageAccountNames(self):
        return self.configData.get("account.names")

    def getStorageAccountKey(self, name):
        return self.configData.get("{0}.minute.key".format(name))
        
    def getStorageAccountType(self, name):
        key = "{0}.minute.ispremium".format(name) 
        return "Premium" if self.configData.get(key) == 1 else "Standard"
    
    def getStorageHostBase(self, name):
        return get_host_base_from_uri(self.getStorageAccountMinuteUri(name)) 

    def getStorageAccountMinuteUri(self, name):
        return self.configData.get("{0}.minute.uri".format(name))

    def getStorageAccountMinuteTable(self, name):
        uri = self.getStorageAccountMinuteUri(name)
        pos = uri.rfind('/')
        tableName = uri[pos+1:]
        return tableName

    def getStorageAccountHourUri(self, name):
        return self.configData.get("{0}.hour.uri".format(name))

    def isLADEnabled(self):
        flag = self.configData.get("wad.isenabled")
        return flag == "1" or flag == 1

    def getLADKey(self):
        return self.configData.get("wad.key")

    def getLADName(self):
        return self.configData.get("wad.name")
    
    def getLADHostBase(self):
        return get_host_base_from_uri(self.getLADUri())

    def getLADUri(self):
        return self.configData.get("wad.uri")

