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
import traceback
import time
import platform

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

MonitoringInterval = 10 * 60 #Ten minutes

class LADDataSource(object):
    pass

class LinuxDataSource(object):
    pass

class StorageDataSource(object):
    pass

class StaticDataSource(object):
    def __init__(self, config):
        self.config = config

    def collect(self):
        counters = [];
        counters.append(self.getCpuOverCommitted())
        counters.append(self.getMemoryOverCommitted())
        counters.append(self.getDataProviderVersion())
        counters.append(self.getDataSources())
        counters.append(self.getInstanceType())
        counters.append(self.getLastHardwareChange())
        counters.append(self.getVirtualizationSolution())
        counters.append(self.getVirtualizationSolutionVersion())
        return counters
    
    def getCloudProvider(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Cloud Provider",
                           value = "Microsoft Azure")

    def getVirtualizationSolutionVersion(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Virtualization Solution Version",
                           value = "")

    def getVirtualizationSolution(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Virtualization Solution",
                           value = "")

    def getLastHardwareChange(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Last Hardware Change",
                           value = time.time(),
                           unit="posixtime")

    def getInstanceType(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Instance Type",
                           value = self.config.getVmSize())

    def getDataSources(self):
        dataSource = "lad" if self.config.isLADEnabled() else "local"
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Data Sources",
                           value = dataSource)

    def getDataProviderVersion(self):
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Data Provider Version",
                           value = AzureEnhancedMonitorVersion)

    def getMemoryOverCommitted(self):
        value = "yes" if self.config.isMemoryOverCommitted() else "no",
        return PerfCounter(counterType = PerfCounterType.COUNTER_TYPE_STRING,
                           category = "config",
                           name = "Memory Over-Provisioning",
                           value = value)

    def getCpuOverCommitted(self):
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
                 machine,
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
        self.machine = machine

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
        if config.ladEnabled():
            self.dataSources.append(LADDataSource(config))
        else:
            self.dataSources.append(LinuxDataSource(config))

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
