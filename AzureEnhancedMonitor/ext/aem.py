#!/usr/bin/env python
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
#
# Requires Python 2.6+
#
import os
import re
import sys
import socket
import traceback
import time
import datetime
import psutil
from azure.storage import TableService, Entity
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

MonitoringIntervalInMinute = 1 #One minute
MonitoringInterval = 60 * MonitoringIntervalInMinute

#It takes sometime before the performance date reaches azure table.
AzureTableDelayInMinute = 5 #Five minute
AzureTableDelay = 60 * AzureTableDelayInMinute

AzureEnhancedMonitorVersion = "1.0.0"
LibDir = "/var/lib/AzureEnhancedMonitor"

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
    startTimestamp = int((unixTime - Epoch).total_seconds())
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

def getAzureDiagnosticCPUData(accountName, accountKey, 
                              startKey, endKey, hostname):
    try:
        waagent.Log("Retrieve diagnostic data(CPU).")
        table = "LinuxPerfCpuVer1v0"
        tableService = TableService(account_name = accountName, 
                                    account_key = accountKey)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}' "
                   "and Host eq '{2}'").format(startKey, endKey, hostname)
        oselect = ("PercentProcessorTime,Host")
        data = tableService.query_entities(table, ofilter, oselect, 1)
        if data is None or len(data) == 0:
            return None
        cpuPercent = float(data[0].PercentProcessorTime)
        return cpuPercent
    except Exception, e:
        waagent.Error(("Failed to retrieve diagnostic data(CPU): {0} {1}"
                       "").format(e, traceback.format_exc()))
        return None
    

def getAzureDiagnosticMemoryData(accountName, accountKey, 
                                 startKey, endKey, hostname):
    try:
        waagent.Log("Retrieve diagnostic data: Memory")
        table = "LinuxPerfMemVer1v0"
        tableService = TableService(account_name = accountName, 
                                    account_key = accountKey)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}' "
                   "and Host eq '{2}'").format(startKey, endKey, hostname)
        oselect = ("PercentAvailableMemory,Host")
        data = tableService.query_entities(table, ofilter, oselect, 1)
        if data is None or len(data) == 0:
            return None
        memoryPercent = 100 - float(data[0].PercentAvailableMemory)
        return memoryPercent
    except Exception, e:
        waagent.Error(("Failed to retrieve diagnostic data(Memory): {0} {1}"
                       "").format(e, traceback.format_exc()))
        return None

class AzureDiagnosticData(object):
    def __init__(self, config):
        self.config = config
        accountName = config.getLADName()
        accountKey = config.getLADKey()
        hostname = socket.gethostname()
        startKey, endKey = getAzureDiagnosticKeyRange()
        self.cpuPercent = getAzureDiagnosticCPUData(accountName, 
                                                    accountKey,
                                                    startKey,
                                                    endKey,
                                                    hostname)
        self.memoryPercent = getAzureDiagnosticMemoryData(accountName, 
                                                          accountKey,
                                                          startKey,
                                                          endKey,
                                                          hostname)

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

    def getNetworkReadBytes(self):
        return self.linux.getNetworkReadBytes()

    def getNetworkWriteBytes(self):
        return self.linux.getNetworkWriteBytes()

    def getNetworkPacketRetransmitted(self):
        return self.linux.getNetworkPacketRetransmitted()
  
    def getLastHardwareChange(self):
        return self.linux.getLastHardwareChange()

class CPUInfo(object):

    @staticmethod
    def getCPUInfo():
        return CPUInfo(waagent.GetFileContents("/proc/cpuinfo"))

    def __init__(self, cpuinfo):
        self.cpuinfo = cpuinfo
        self.lines = cpuinfo.split("\n")

        lps = filter(lambda x : re.match("processor\s+:\s+\d+$", x), 
                              self.lines)
        self.numOfLogicalProcessors = len(lps)

        coresPerCPU = re.search("cpu cores\s+:\s+(\d+)", self.cpuinfo)
        self.numOfCoresPerCPU = int(coresPerCPU.group(1))

        cpuIds = filter(lambda x : re.match("physical id\s+:\s+(\d+)$", x), 
                        self.lines)
        self.physCPUs = len(set(cpuIds))
        self.numOfCores = self.physCPUs * self.numOfCoresPerCPU

        model = re.search("model name\s+:\s+(.*)\s", self.cpuinfo)
        vendorId = re.search("vendor_id\s+:\s+(.*)\s", self.cpuinfo)
        self.processorType = "{0}, {1}".format(model.group(1), vendorId.group(1))
        
        freq = re.search("cpu MHz\s+:\s+(.*)\s", self.cpuinfo)
        self.frequency = float(freq.group(1))

        ht = re.match("flags\s.*\sht\s", self.cpuinfo)
        self.isHTon = ht is not None

    def getNumOfLogicalProcessors(self):
        return self.numOfLogicalProcessors
    
    def getNumOfCoresPerCPU(self):
        return self.numOfCoresPerCPU
    
    def getNumOfCores(self):
        return self.numOfCores
    
    def getNumOfPhysCPUs(self):
        return self.physCPUs

    def getProcessorType(self):
        return self.processorType
   
    def getFrequency(self):
        return self.frequency

    def isHyperThreadingOn(self):
        return self.isHTon

    def getCPUPercent(self):
        return psutil.cpu_percent()

    def __str__(self):
        return "Phys CPUs    : {0}\n".format(self.getNumOfPhysCPUs())+\
               "Cores / CPU  : {0}\n".format(self.getNumOfCoresPerCPU())+\
               "Cores        : {0}\n".format(self.getNumOfCores())+\
               "Threads      : {0}\n".format(self.getNumOfLogicalProcessors())+\
               "Model        : {0}\n".format(self.getProcessorType())+\
               "Frequency    : {0}\n".format(self.getFrequency())+\
               "Hyper Thread : {0}\n".format(self.isHyperThreadingOn())+\
               "CPU Usage    : {0}\n".format(self.getCPUPercent())

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
        self.readBytes = 0
        self.writeBytes = 0
        for nicName, stat in self.nics.iteritems():
            if nicName != 'lo':
                self.nicNames.append(nicName)
                self.readBytes = self.readBytes + stat[1] #bytes_recv
                self.writeBytes = self.writeBytes + stat[0] #bytes_sent

    def getAdapterIds(self):
        return self.nicNames

    def getNetworkReadBytes(self):
        return self.readBytes

    def getNetworkWriteBytes(self):
        return self.writeBytes

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
        lps = self.cpuInfo.getNumOfLogicalProcessors()
        cores = self.cpuInfo.getNumOfCores()
        return lps / cores

    def getPhysProcessingPowerPerVCPU(self):
        cores = self.cpuInfo.getNumOfCores()
        lps = self.cpuInfo.getNumOfLogicalProcessors()
        return float(cores) / lps

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

    def getNetworkReadBytes(self):
        return self.networkInfo.getNetworkReadBytes()

    def getNetworkWriteBytes(self):
        return self.networkInfo.getNetworkWriteBytes()

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
            counters.append(self.createCounterAdapterId(adapterId))
            counters.append(self.createCounterNetworkMapping(metrics, adapterId))
            counters.append(self.createCounterMinNetworkBandwidth(metrics, 
                                                                  adapterId))
            counters.append(self.createCounterMaxNetworkBandwidth(metrics,
                                                                  adapterId))
        counters.append(self.createCounterNetworkReadBytes(metrics))
        counters.append(self.createCounterNetworkWriteBytes(metrics))
        counters.append(self.createCounterNetworkPacketRetransmitted(metrics))
        
        #Hardware change
        counters.append(self.createCounterLastHardwareChange(metrics))
        return counters
    
    def createCounterLastHardwareChange(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "config",
                           name = "Last Hardware Change",
                           value = metrics.getLastHardwareChange(),
                           unit="posixtime")

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
                           name = "Maximum Network Bandwidth",
                           instance = adapterId,
                           value = metrics.getMaxNetworkBandwidth(adapterId),
                           unit = "Mbit/s")

    def createCounterMinNetworkBandwidth(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Minimum Network Bandwidth",
                           instance = adapterId,
                           value = metrics.getMinNetworkBandwidth(adapterId),
                           unit = "Mbit/s")

    def createCounterNetworkReadBytes(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "network",
                           name = "Network Read Bytes",
                           value = metrics.getNetworkReadBytes(),
                           unit = "byte/s")

    def createCounterNetworkWriteBytes(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "network",
                           name = "Network Write Bytes",
                           value = metrics.getNetworkWriteBytes(),
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

def getStorageMetrics(account, key, table, startKey, endKey):
    try:
        waagent.Log("Retrieve storage metrics data.")
        tableService = TableService(account_name = account, account_key = key)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}'"
                   "").format(startKey, endKey)
        oselect = ("TotalRequests,TotalIngress,TotalEgress,AverageE2ELatency,"
                   "AverageServerLatency,RowKey")
        metrics = tableService.query_entities(table, ofilter, oselect)
        waagent.Log("{0} records returned.".format(len(metrics)))
        return metrics
    except Exception, e:
        waagent.Error(("Failed to retrieve storage metrics data: {0} {1}"
                       "").format(e, traceback.format_exc()))
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
        diskMapping = {
                "/dev/sda": osdiskVhd,
                "/dev/sdb": "not mapped to vhd"
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
            vhd = "{0} {1}".format(self.config.getDataDiskAccount(i),
                                   self.config.getDataDiskName(i))
            if lun in lunToDevMap:
                dev = lunToDevMap[lun]
                diskMapping[dev] = vhd
            else:
                waagent.Warn("Couldn't find disk with lun: {0}".format(lun))

        return diskMapping 

def isUserRead(op):
    if not op.startswith("user;"):
        return False
    op = op[5:]
    for prefix in {"Get", "List", "Preflight"}:
        if op.startswith(prefix):
            return True
    return False

def isUserWrite(op):
    if not op.startswith("user;"):
        return False
    op = op[5:]
    for prefix in {"Put" ,"Set" ,"Clear" ,"Delete" ,"Create" ,"Snapshot"}:    
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
    stat['throughput'] = stat['bytes'] / (1024 * 1024) / 60 
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
        diskMapping = DiskInfo(self.config).getDiskMapping()
        for dev, vhd in diskMapping.iteritems():
            counters.append(self.createCounterDiskMapping(dev, vhd)) 

        accounts = self.config.getStorageAccountNames()
        startKey, endKey = getStorageTableKeyRange()
        for account in accounts:
            tableName = self.config.getStorageAccountMinuteTable(account)
            accountKey = self.config.getStorageAccountKey(account)
            metrics = getStorageMetrics(account, 
                                        accountKey,
                                        tableName,
                                        startKey,
                                        endKey)
            stat = AzureStorageStat(metrics)
            counters.append(self.createCounterStorageId(account))
            counters.append(self.createCounterReadBytes(account, stat))
            counters.append(self.createCounterReadOps(account, stat))
            counters.append(self.createCounterReadOpE2ELatency(account, stat))
            counters.append(self.createCounterReadOpServerLatency(account, 
                                                                  stat))
            counters.append(self.createCounterReadOpThroughput(account, stat))
            counters.append(self.createCounterWriteBytes(account, stat))
            counters.append(self.createCounterWriteOps(account, stat))
            counters.append(self.createCounterWriteOpE2ELatency(account, stat))
            counters.append(self.createCounterWriteOpServerLatency(account, 
                                                                   stat))
            counters.append(self.createCounterWriteOpThroughput(account, stat))
        return counters

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
        print ret
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
        return counters
  
     
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
        dataSource = "lad" if self.config.isLADEnabled() else "local"
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
            except IOError, e:
                waagent.Warn("Write to event file failed: {0}".format(e))
                waagent.Log("Retry: {0}".format(i))
        
        raise IOError(("Couldn't serialize event to event file:{0}"
                         "").format(eventFile))

    def _write(self, counters, eventFile):
        with open(eventFile, "w+") as F:
            F.write("".join(map(lambda c : str(c), counters)).encode("utf8"))

class EnhancedMonitorConfig(object):
    def __init__(self, configData):
        self.configData = configData

    def getVmSize(self):
        return self.configData["vm.size"]

    def getVmRoleInstance(self):
        return self.configData["vm.roleinstance"]

    def getVmDeploymentId(self):
        return self.configData["vm.depoymentId"]

    def isMemoryOverCommitted(self):
        return self.configData["vm.memory.isovercommitted"]

    def isCpuOverCommitted(self):
        return self.configData["vm.cpu.isovercommitted"]

    def getScriptVersion(self):
        return self.configData["script.version"]

    def isVerbose(self):
        return self.configData["verbose"]

    def getOSDiskName(self):
        return self.configData["osdisk.name"]

    def getOSDiskAccount(self):
        return self.configData["osdisk.account"]

    def getOSDiskConnMinute(self):
        return self.configData["osdisk.connminute"]

    def getOSDiskConnHour(self):
        return self.configData["osdisk.connhour"]
    
    def getDataDiskCount(self):
        return self.configData["disk.count"]

    def getDataDiskLun(self, index):
        return self.configData["disk.lun.{0}".format(index)]

    def getDataDiskName(self, index):
        return self.configData["disk.name.{0}".format(index)]

    def getDataDiskAccount(self, index):
        return self.configData["disk.account.{0}".format(index)]

    def getDataDiskConnMinute(self, index):
        return self.configData["disk.connminute.{0}".format(index)]

    def getDataDiskConnHour(self, index):
        return self.configData["disk.connhour.{0}".format(index)]

    def getStorageAccountNames(self):
        return self.configData["account.names"]

    def getStorageAccountKey(self, name):
        return self.configData["{0}.minute.key".format(name)]

    def getStorageAccountMinuteUri(self, name):
        return self.configData["{0}.minute.uri".format(name)]

    def getStorageAccountMinuteTable(self, name):
        uri = self.getStorageAccountMinuteUri(name)
        pos = uri.rfind('/')
        tableName = uri[pos+1:]
        return tableName

    def getStorageAccountHourUri(self, name):
        return self.configData["{0}.hour.uri".format(name)]

    def isLADEnabled(self):
        return self.configData["lad.isenabled"]

    def getLADKey(self):
        return self.configData["lad.key"]

    def getLADName(self):
        return self.configData["lad.name"]

    def getLADUri(self):
        return self.configData["lad.uri"]

