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
import socket
import traceback
import time
import platform
from azure.storage import TableService, Entity
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

MonitoringInterval = 10 * 60 #Ten minutes

class AzureDiagnosticMetric(object):
    def __init__(self, config):
        self.config = config

class LinuxMetric(object):
    def __init__(self, config):
        self.config = config
    
    def getNetworkAdapterMetrics(self):
        pass

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
        oselect = "TotalRequests,TotalIngress,TotalEgress,AverageE2ELatency,"
                  "AverageServerLatency"
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
        adapters = metrics.getNetworkAdapterMetrics()
        for adapter in adapters:
            counters.append(self.createCounterAdapterId(adapter))
            counters.append(self.createCounterNetworkMapping(adapter))
            counters.append(self.createCounterMinNetworkBandwidth(adapter))
            counters.append(self.createCounterMaxNetworkBandwidth(adapter))
            counters.append(self.createCounterNetworkReadBytes(adapter))
            counters.append(self.createCounterNetworkWriteBytes(adapter))
            counters.append(self.createCounterNetworkPacketRetransmitted(adapter))

        return counters
    
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
                           value = metrics.getCurrHwFrequency(),
                           unit = "compute unit")

    def createCounterMaxVMProcessingPower(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Max VM Processing Power",
                           value = metrics.getMaxHwFrequency(),
                           unit = "compute unit")

    def createCounterGuaranteedVMProcessingPower(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "cpu",
                           name = "Guaranteed VM Processing Power",
                           value = metrics.getGuaranteedHwFrequency(),
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
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
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

    def createCounterAdapterId(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Adapter Id",
                           instance = adapter.getAdapterId(),
                           value = adapter.getAdapterId())

    def createCounterNetworkMapping(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Mapping",
                           instance = adapter.getAdapterId(),
                           value = adapter.getAdapterId())

    def createCounterMaxNetworkBandwidth(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Maximum Network Bandwidth",
                           instance = adapter.getAdapterId(),
                           value = adapter.getMaxNetworkBandwidth(),
                           unit = "Mbit/s")

    def createCounterMinNetworkBandwidth(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Minimum Network Bandwidth",
                           instance = adapter.getAdapterId(),
                           value = adapter.getMinNetworkBandwidth(),
                           unit = "Mbit/s")

    def createCounterNetworkReadBytes(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Network Read Bytes",
                           instance = adapter.getAdapterId(),
                           value = adapter.getNetworkReadBytes(),
                           unit = "byte/s")

    def createCounterNetworkWriteBytes(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Network Write Bytes",
                           instance = adapter.getAdapterId(),
                           value = adapter.getNetworkWriteBytes(),
                           unit = "byte/s")

    def createCounterNetworkPacketRetransmitted(self, adapter):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_INT,
                           category = "network",
                           name = "Packets Retransmitted",
                           instance = adapter.getAdapterId(),
                           value = adapter.getNetworkPacketRetransmitted(),
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
        for root, path, dev in self.getBlockDevices()
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
                           unit = 'ms'
                           refreshInterval = 60)

    def createCounterReadOpServerLatency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Op Latency Server msec",
                           instance = metrics.getAccount(),
                           value = metrics.getReadOpServerLatency(),
                           unit = 'ms'
                           refreshInterval = 60)

    def createCounterReadOpThroughput(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Read Throughput E2E MB/sec",
                           instance = metrics.getAccount(),
                           value = metrics.getReadOpThroughput(),
                           unit = 'MB/s'
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
                           unit = 'ms'
                           refreshInterval = 60)

    def createCounterWriteOpServerLatency(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Op Latency Server msec",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteOpServerLatency(),
                           unit = 'ms'
                           refreshInterval = 60)

    def createCounterWriteOpThroughput(self, metrics):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_DOUBLE,
                           category = "storage",
                           name = "Storage Write Throughput E2E MB/sec",
                           instance = metrics.getAccount(),
                           value = metrics.getWriteOpThroughput(),
                           unit = 'MB/s'
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
        counters.append(self.createCounterCpuOverCommitted())
        counters.append(self.createCounterMemoryOverCommitted())
        counters.append(self.createCounterDataProviderVersion())
        counters.append(self.createCounterDataSources())
        counters.append(self.createCounterInstanceType())
        counters.append(self.createCounterLastHardwareChange())
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

    def createCounterLastHardwareChange(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Last Hardware Change",
                           value = time.time(),
                           unit="posixtime")

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
        value = "yes" if self.config.isMemoryOverCommitted() else "no",
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Memory Over-Provisioning",
                           value = value)

    def createCounterCpuOverCommitted(self):
        value = "yes" if self.config.isCpuOverCommitted() else "no",
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
                 refreshInverval=0):
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
        return u(";{0};{1};{2};{3};{4};{5};{6};{7};{8};"
                 "").format(counterType,
                            source,
                            name,
                            instance,
                            value,
                            unit,
                            refreshInterval,
                            timestamp,
                            machine)

    __repr__ = __str__
        

class EnhancedMonitor(object):
    def __init__(self, config):
        self.dataSources = []
        self.dataSources.append(VMDataSource(config))
        self.dataSources.append(StorageDataSource(config))
        self.dataSources.append(StaticDataSource(config))

    def run(self):
        counters = []
        for dataSource in self.dataSource:
            try:
                counters.extend(counters, dataSource.collect())
            except Exception, e:
                waagent.Error("{0} {1}".format(e, traceback.format_exc()))
        return counters

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
    waagent.Log("Monitor service started.")
    monitor = EnhancedMonitor()
    writer = PerfCounterWriter()
    while True:
        waagent.Log("Collecting performance counter.")
        try:
            counters = monitor.run()
            writer.write(counters)
            #TODO do status report
        except Exception, e:
            waagent.Error("{0} {1}".format(e, traceback.format_exc()))
        waagent.Log("Finished collection.")
        time.sleep(MonitoringInterval)
