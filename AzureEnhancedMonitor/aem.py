#!/usr/bin/env python
#
#CustomScript extension
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
import re
import socket
import traceback
import time
import platform
from azure.storage import TableService, Entity
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

MonitoringInterval = 60 #One minute
AzureEnhancedMonitorVersion = "1.0.0"

class AzureDiagnosticMetric(object):
    def __init__(self, config):
        self.config = config

class CPUInfo(object):
    def __init__(self, cpuinfo):
        self.cpuinfo = cpuinfo
        self.lines = cpuinfo.split("\n")

    def getNumOfLogicalProcessor(self):
        lps = filter(lambda x : re.match("processor\s+:\s+\d+$", x), 
                       self.lines)
        return len(lps)
    
    def getNumOfCoresPerCPU(self):
        numOfCoresPerCPU = re.match("cpu cores\s+:\s+(.*)$", self.cpuinfo)
        return int(numOfCoresPerCPU.group(1))
    
    def getNumOfPhysCPUs(self):
        cpus = filter(lambda x : re.match("physical id\s+:\s+(\d+)$", x), 
                      self.lines)
        return len(set(cpus))

    def getModel(self):
        model = re.match("model name\s+:\s+(.*)\s", self.cpuinfo)
        return model.group(1)
    
    def getVendorId(self):
        vendorId = re.match("vendor_id\s+:\s+(.*)\s", self.cpuinfo)
        return vendorId.group(1)

    def getFrequency(self):
        freq = re.match("cpu MHz\s+:\s+(.*)\s", self.cpuinfo)
        return float(freq.group(1))

    def isHyperThreadingOn(self):
        freq = re.match("flags\s.*\sht\s", self.cpuinfo)
        return freq is not None

class LinuxMetric(object):

    def __init__(self, config):
        self.config = config
        #CPU
        cpuInfo = CPUInfo(getCPUInfo())
        self.frequency = cpuInfo.getFrequency()
        self.numOfLogicalProcessors = cpuInfo.getNumOfLogicalProcessor()
        self.numOfCoresPerCPU = cpuInfo.getNumOfCoresPerCPU()
        self.numOfPhysCPUs = cpuInfo.getNumOfPhysCPUs()
        self.numOfCores = self.numOfCoresPerCPU() * self.numOfPhysCPUs()
        self.numOfLPPerCore = self.numOfLogicalProcessors / self.numOfCores
        self.processorType = "{0}, {1}".format(cpuInfo.getModel(),
                                               cpuInfo.getVendorId())
        if cpuInfo.isHyperThreadingOn():
            self.vCPUMapping = "thread"
        else:
            self.vCPUMapping = "core"
    
        #Memory
        self.cpuPercent = psutil.cpu_percent() * 100
        self.memInfo = psutil.virtual_memory()
        self.memSize = memInfo[0] / 1024 /1024 #MB
        self.memPercent =  memInfo[2] #%

        #Network
        self.nics = psutil.net_io_counters()
        self.nicNames = []
        self.readBytes = 0
        self.writeBytes = 0
        for nicName, stat in self.nics.iteritems():
            if nicName != 'lo':
                self.nicNames.append(nicName)
                self.readBytes = self.readBytes + stat[1] #bytes_recv
                self.writeBytes = self.writeBytes + stat[0] #bytes_sent

    def getCPUInfo():
        return waagent.GetFileContents("/proc/cpuinfo") 

    def getMacAddress(adapterId):
        nicAddrPath = os.path.join("/sys/class/net", adapterId, "address")
        mac = waagent.GetFileContents(nicAddrPath)
        return mac

    def getNetstat():
        retCode, output = waagent.RunGetOutput("netstat -s")
        if retCode == 0:
            return output
        else:
            waagent.Error("Can't get netstat output: {0}, {1}".format(retCode,
                                                                      output))
            return None
   
    HwInfoFile = "/var/lib/waagent/HwInfo"
    def getHwInfo():
        if not os.path.isfile(HwInfoFile):
            return None, None
        hwInfo = waagent.GetFileContents(HwInfoFile).split("\n")
        return int(hwInfo[0]), hwInfo[1:]

    def setHwInfo(timestamp, hwInfo):
        content = str(timestamp)
        content = content + "\n".join(hwInfo)
        waagent.SetFileContents(HwInfoFile, content)

    def sameList(l1, l2):
        if l1 is None or l2 is None:
            return l1 == l2
        if len(l1) != len(l2):
            return False
        for i in range(0, len(l1)):
            if l1[i] != l2[i]:
                return False
        return True

    def getLastHardwareChange(self):
        oldTime, oldMacs = getHwInfo()
        newMacs = map(lambda x : getMacAddress(x), self.nicNames)
        newTime = time.utctime()
        newMacs.sort()
        if not sameList(newMacs, oldMacs):
            #Hardware changed
            if newTime < oldTime:
                waagent.Error(("Hardware change detected. But the old timestamp "
                               "is greater than now, {0}>{1}.").format(oldTime, 
                                                                       newTime))
            setHwInfo(newTime, newMacs)
            return newTime
        else:
            return None

    def getCurrHwFrequency(self):
        return self.frequency

    def getMaxHwFrequency(self):
        return self.frequency

    def getMaxVMProcessingPower(self):
        return self.numOfCores

    def getCurrVMProcessingPower(self):
        return self.numOfCores if self.config.isCpuOverCommitted() else None

    def getGuaranteedMemAssigned(self):
        return self.getCurrMemAssigned()

    def getNumOfCoresPerCPU(self):
        return self.numOfCoresPerCPU

    def getNumOfThreadsPerCore(self):
        return self.numOfLPPerCore

    def getPhysProcessingPowerPerVCPU(self):
        return float(self.numOfCores) / self.numOfLogicalProcessors

    def getProcessorType(self):
        return self.processorType

    def getReferenceComputeUnit(self):
        return self.processorType

    def getVCPUMapping(self):
        return self.vCPUMapping()
    
    def getVMProcessingPowerConsumption(self):
        return self.memPercent
    
    def getCurrMemAssigned(self):
        return memSize if self.config.isMemoryOverCommitted() else None

    def getMaxMemAssigned(self):
        return memSize

    def getGuaranteedMemAssigned(self):
        return self.getCurrMemAssigned()

    def getVMMemConsumption(self):
        return self.memPercent

    def getAdapterIds(self):
        return self.nicNames

    def getAdapterMapping(self, adapterId):
        mac = getMacAddress(adapterId)
        mac = mac.replace(":", "-")
        return mac

    def getMaxNetworkBandwidth(self, adapterId):
        return 1000 #Mbit/s 

    def getMinNetworkBandwidth(self, adapterId):
        return 1000 #Mbit/s 

    def getNetworkReadBytes(self):
        return self.readBytes

    def getNetworkWriteBytes(self):
        return self.writeBytes

    def getNetworkPacketRetransmitted(self):
        netstat = getNetstat()
        match = re.match("(\d)+\s*segments retransmited")
        if match != None:
            return int(match.group(1))
        else:
            waagent.Error("Failed to parse netstat output: {0}".format(netstat))
            return None
  
class StorageMetric(object):

    def isUserRead(op):
        if not op.startswith("user;"):
            return False
        op = op[5:]
        return op in {"Get", "List", "Preflight"}            

    def isUserWrite(op):
        if not op.startswith("user;"):
            return False
        op = op[5:]
        return op in {"Put" ,"Set" ,"Clear" ,"Delete" ,"Create" ,"Snapshot"}    

    def stat(metrics, opFilter):
        metrics = filter(lambda x : opFilter(x), metrics)
        stat = {}
        stat['bytes'] = sum(map(lambda x : x.TotalIngress + x.TotalEgress, 
                                metrics))
        stat['ops'] = sum(map(lambda x : x.TotalRequests, readOps))
        stat['e2eLatency'] = sum(map(lambda x : x.TotalRequests * \
                                                x.AverageE2ELatency, 
                                     metrics)) / stat['ops']
        stat['serverLatency'] = sum(map(lambda x : x.TotalRequests * \
                                                   x.AverageServerLatency, 
                                        metrics)) / stat['ops']
        #Convert to MB/s
        stat['throughput'] = stat['bytes'] / (1024 * 1024) / 60 
        return stat

    def __init__(self, account, key, table, startKey, endKey):
        tableService = TableService(account_name = account, account_key = key)
        ofilter = ("PartitionKey ge '{0}' and PartitionKey lt '{1}'"
                   "").format(startKey, endKey)
        oselect = ("TotalRequests,TotalIngress,TotalEgress,AverageE2ELatency,"
                   "AverageServerLatency")
        metrics = tableService.query_entities(table, ofilter, oselect)
        self.account = account
        self.rStat = stat(metrics, isUserRead)
        self.wStat = stat(metrics, isUserWrite)

    def getAccount(self):
        return self.account

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

class VMDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = []
        if self.config.isLADEnabled():
            metrics = AzureDiagnosticMetric(self.config)
        else:
            metrics = LinuxMetric(self.config)

        counters.append(self.createCounterLastHardwareChange(metrics))

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

        return counters
    
    def createCounterLastHardwareChange(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_LARGE,
                           category = "config",
                           name = "Last Hardware Change",
                           value = metrics.getLastHardwareChange(),
                           unit="posixtime")

    def createCounterCurrHwFrequency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Current Hw Frequency",
                           value = metrics.getCurrHwFrequency(),
                           unit = "MHz",
                           refreshInterval = 60)

    def createCounterMaxHwFrequency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
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
                           name = "Max VM Processing Power",
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
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Processor Type",
                           value = metrics.getProcessorType())

    def createCounterReferenceComputeUnit(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Reference Compute Unit",
                           value = metrics.getReferenceComputeUnit())

    def createCounterVCPUMapping(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "vCPU Mapping",
                           value = metrics.getVCPUMapping())

    def createCounterVMProcessingPowerConsumption(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "VM Processing Power Consumption",
                           value = metrics.getVMProcessingPowerConsumption(),
                           unit = "%",
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
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "memory",
                           name = "VM Memory Consumption",
                           value = metrics.getVMMemConsumption(),
                           unit = "%",
                           refreshInterval = 60)

    def createCounterAdapterId(self, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Adapter Id",
                           instance = adapterId,
                           value = adapterId)

    def createCounterNetworkMapping(self, metrics, adapterId):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Mapping",
                           instance = adapterId,
                           value = metrics.getAdapterMapping(adapterId))

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
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Network Read Bytes",
                           value = metrics.getNetworkReadBytes(),
                           unit = "byte/s")

    def createCounterNetworkWriteBytes(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
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

class StorageDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = []
        diskMapping = self.getDiskMapping()
        for dev, vhd in diskMapping.iteritems():
            counters.append(self.createCounterDiskMappingCounter(dev, vhd)) 
        accounts = self.config.getStorageAccountNames()
        for account in accounts:
            metrics = self.getStorageMetrics(account)
            counters.append(self.createCounterStorageId(account))
            counters.append(self.createCounterReadBytes(metrics))
            counters.append(self.createCounterReadOps(metrics))
            counters.append(self.createCounterReadOpE2ELatency(metrics))
            counters.append(self.createCounterReadOpServerLatency(metrics))
            counters.append(self.createCounterReadOpThroughput(metrics))
            counters.append(self.createCounterWriteBytes(metrics))
            counters.append(self.createCounterWriteOps(metrics))
            counters.append(self.createCounterWriteOpE2ELatency(metrics))
            counters.append(self.createCounterWriteOpServerLatency(metrics))
            counters.append(self.createCounterWriteOpThroughput(metrics))
        return counters

    def getDiskMapping(self):
        osdiskVhd = "{0} {1}".format(self.config.getOSDiskAccount(),
                                  self.config.getOSDiskName())
        diskMapping = {
                "/dev/sda": osdiskVhd,
                "/dev/sdb": "not mapped to vhd"
        }

        dataDisks = {}
        for root, path, dev in self.getBlockDevices():
            if re.match("sd[c-z]", dev):
                lun = self.getFirstLun(dev)
                dataDisks[lun] = dev

        diskCount = self.config.getDataDiskCount()
        for i in range(0, diskCount):
            lun = self.config.getDataDiskLun(i)
            vhd = "{0} {1}".format(self.config.getDataDiskAccount(i),
                                   self.config.getDataDiskName(i))
            if lun in dataDisks:
                dev = dataDisks[lun]
                diskMapping[dev] = vhd

        return diskMapping 

    def getBlockDevices(self):
        return os.walk("/sys/block")

    def getFirstLun(self, dev):
        path = os.path.join("/sys/block", dev, "device/scsi_disk")
        for lun in os.listdir(path):
            return lun

    def getStorageMetrics(self, account):
        uri = self.config.getStorageAccountMinuteUri()
        pos = uri.rfind('/')
        tableName = uri[pos+1:]

        now = time.gmtime()
        keyFormat = "{0:0>4d}{1:0>2d}{2:0>2d}T{3:0>2d}{4:0>2d}"
        startKey = keyFormat.format(now.tm_year, 
                                    now.tm_mon, 
                                    now.tm_mday,
                                    now.tm_hour,
                                    now.tm_min - 1)
        endKey = keyFormat.format(now.tm_year, 
                                  now.tm_mon, 
                                  now.tm_mday,
                                  now.tm_hour,
                                  now.tm_min)
        return StorageMetric(account, 
                             self.config.getStorageAccountKey(account),
                             tableName,
                             startKey,
                             endKey)

    def createCounterReadBytes(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "storage",
                           name = "Storage Read Bytes",
                           instance = metrics.getAccount(),
                           value = metrics.getReadBytes(),
                           unit = 'byte',
                           refreshInterval = 60)

    def createCounterReadOps(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "storage",
                           name = "Storage Read Ops",
                           instance = metrics.getAccount(),
                           value = metrics.getReadOps(),
                           refreshInterval = 60)

    def createCounterReadOpE2ELatency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Op Latency E2E msec",
                           instance = metrics.getAccount(),
                           value = metrics.getReadOpE2ELatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterReadOpServerLatency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Op Latency Server msec",
                           instance = metrics.getAccount(),
                           value = metrics.getReadOpServerLatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterReadOpThroughput(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Throughput E2E MB/sec",
                           instance = metrics.getAccount(),
                           value = metrics.getReadOpThroughput(),
                           unit = 'MB/s',
                           refreshInterval = 60)

    def createCounterWriteBytes(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "storage",
                           name = "Storage Write Bytes",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteBytes(),
                           unit = 'byte',
                           refreshInterval = 60)

    def createCounterWriteOps(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "storage",
                           name = "Storage Write Ops",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteOps(),
                           refreshInterval = 60)

    def createCounterWriteOpE2ELatency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Op Latency E2E msec",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteOpE2ELatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterWriteOpServerLatency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Op Latency Server msec",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteOpServerLatency(),
                           unit = 'ms',
                           refreshInterval = 60)

    def createCounterWriteOpThroughput(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Throughput E2E MB/sec",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteOpThroughput(),
                           unit = 'MB/s',
                           refreshInterval = 60)


    def createCounterStorageId(self, account):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "storage",
                           name = "Storage ID",
                           instance = account,
                           value = value)

    def createCounterDiskMapping(self, dev, vhd):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "storage",
                           name = "Phys. Disc to Storage Mapping",
                           instance = dev,
                           value = vhd)

class StaticDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = [];
        counters.append(self.createCounterCloudProvider())
        counters.append(self.createCounterCpuOverCommitted())
        counters.append(self.createCounterMemoryOverCommitted())
        counters.append(self.createCounterDataProviderVersion())
        counters.append(self.createCounterDataSources())
        counters.append(self.createCounterInstanceType())
        counters.append(self.createCounterVirtualizationSolution())
        counters.append(self.createCounterVirtualizationSolutionVersion())
        return counters
  
     
    def createCounterCloudProvider(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Cloud Provider",
                           value = "Microsoft Azure")

    def createCounterVirtualizationSolutionVersion(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Virtualization Solution Version",
                           value = "")

    def createCounterVirtualizationSolution(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Virtualization Solution",
                           value = "")
  
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
                 refreshInterval=0):
        self.counterType = counterType
        self.category = category
        self.name = name
        self.instance = instance
        self.value = value
        self.unit = unit
        self.refreshInterval = refreshInterval

        self.timestamp = int(time.time())
        self.machine = socket.gethostname()

    def __str__(self):
        return (u";{0};{1};{2};{3};{4};{5};{6};{7};{8};"
                 "").format(self.counterType,
                            self.category,
                            self.name,
                            self.instance,
                            self.value,
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
        for dataSource in self.dataSource:
            counters.extend(counters, dataSource.collect())
            writer.write(counters)

class PerfCounterWriter(object):
    def write(self, counters):
        pass

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
        return self.configData["{0}.key".format(name)]

    def getStorageAccountMinuteUri(self, name):
        return self.configData["{0}.minute.uri".format(name)]

    def getStorageAccountHourUri(self, name):
        return self.configData["{0}.hour.uri".format(name)]

    def isLADEnabled(self):
        return self.configData["lad.isenable"]

    def getLADKey(self):
        return self.configData["lad.key"]

    def getLADName(self):
        return self.configData["lad.name"]

    def getLADUri(self):
        return self.configData["lad.uri"]

def main():
    hutil = parse_context("Enable")
    monitor = EnhancedMonitor()
    while True:
        waagent.Log("Collecting performance counter.")
        try:
            monitor.run()
            #TODO do status report
        except Exception, e:
            waagent.Error("{0} {1}".format(e, traceback.format_exc()))
        waagent.Log("Finished collection.")
        time.sleep(MonitoringInterval)
