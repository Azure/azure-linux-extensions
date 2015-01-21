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

import unittest
import env
import os
import aem
import json
from Utils.WAAgentUtil import waagent

TestConfig="""{
        "vm.size" : "Small (A1)",
        "vm.roleinstance" : "haha",
        "vm.role" : "hehe",
        "vm.deploymentid" : "should-be-a-guid",
        "vm.memory.isovercommitted" : 0,
        "vm.cpu.isovercommitted" :  0,
        "script.version" : "1.0.0",
        "verbose" : 0,
        "osdisk.name" : "test-aem",
        "osdisk.account" : "test-aem",
        "osdisk.connminute":"",
        "osdisk.connhour":"",
        "disk.count" : 2,
        "disk.lun.1" : 1,
        "disk.name.1" : "test-aem-dd1",
        "disk.account.1" : "test-aem-dd1",
        "disk.connminute.1" : "",
        "disk.connhour.1" : "",
        "disk.lun.2" : 1,
        "disk.name.2" : "test-aem-dd2",
        "disk.account.2" : "test-aem-dd2",
        "disk.connminute.2" : "",
        "disk.connhour.2" : "",
        "account.names" :["testaemstorage"],
        "testaemstorage.key" : "1sdf209unljnlfjahsdlfh===",
        "testaemstorage.hour.uri" : "http://foo.bar/",
        "testaemstorage.minute.uri" : "http://foo.bar/",
        "lad.isenable" : 1,
        "lad.key" : "23rsdf2fzcvf=+12",
        "lad.name" : "asdf",
        "lad.uri": "http://foo.bar/"
}
"""

class TestAEM(unittest.TestCase):
    def setUp(self):
        waagent.LoggerInit("/dev/null", "/dev/stdout")

    def test_config(self):
        configData = json.loads(TestConfig)
        config = aem.EnhancedMonitorConfig(configData)
        self.assertNotEquals(None, config)
        return config

    def test_static_datasource(self):
        config = self.test_config()
        dataSource = aem.StaticDataSource(config)
        counters = dataSource.collect()
        self.assertNotEquals(None, counters)
        self.assertNotEquals(0, len(counters))

        name = "Cloud Provider"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("Microsoft Azure", counter.value)
        
        name = "Virtualization Solution Version"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("", counter.value)

        name = "Virtualization Solution"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("", counter.value)

        name = "Instance Type"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("Small (A1)", counter.value)

        name = "Data Sources"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("lad", counter.value)

        name = "Data Provider Version"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("1.0.0", counter.value)

        name = "Memory Over-Provisioning"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("no", counter.value)

        name = "CPU Over-Provisioning"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("no", counter.value)

    def test_cpuinfo(self):
        cpuinfo = aem.CPUInfo.getCPUInfo()
        self.assertNotEquals(None, cpuinfo)
        self.assertNotEquals(0, cpuinfo.getNumOfPhysCPUs())
        self.assertNotEquals(0, cpuinfo.getNumOfCoresPerCPU())
        self.assertNotEquals(0, cpuinfo.getNumOfCores())
        self.assertNotEquals(0, cpuinfo.getNumOfLogicalProcessors())
        self.assertNotEquals(None, cpuinfo.getProcessorType())
        self.assertEquals(float, type(cpuinfo.getFrequency()))
        self.assertEquals(bool, type(cpuinfo.isHyperThreadingOn()))
        percent = cpuinfo.getCPUPercent()
        self.assertEquals(float, type(percent))
        self.assertTrue(percent >= 0 and percent <= 100)

    def test_meminfo(self):
        meminfo = aem.MemoryInfo()
        self.assertNotEquals(None, meminfo.getMemSize())
        self.assertEquals(long, type(meminfo.getMemSize()))
        percent = meminfo.getMemPercent()
        self.assertEquals(float, type(percent))
        self.assertTrue(percent >= 0 and percent <= 100)

    def test_networkinfo(self):
        netinfo = aem.NetworkInfo()
        adapterIds = netinfo.getAdapterIds()
        self.assertNotEquals(None, adapterIds)
        self.assertNotEquals(0, len(adapterIds))
        adapterId = adapterIds[0]
        self.assertNotEquals(None, aem.getMacAddress(adapterId))
        self.assertNotEquals(None, netinfo.getNetworkReadBytes())
        self.assertNotEquals(None, netinfo.getNetworkWriteBytes())
        self.assertNotEquals(None, netinfo.getNetworkPacketRetransmitted())

    def test_hwchangeinfo(self):
        netinfo = aem.NetworkInfo()
        testHwInfoFile = "/tmp/HwInfo"
        aem.HwInfoFile = testHwInfoFile
        if os.path.isfile(testHwInfoFile):
            os.remove(testHwInfoFile)
        hwChangeInfo = aem.HardwareChangeInfo(netinfo)
        self.assertNotEquals(None, hwChangeInfo.getLastHardwareChange())
        self.assertTrue(os.path.isfile, aem.HwInfoFile)

        #No hardware change
        lastChange = hwChangeInfo.getLastHardwareChange()
        hwChangeInfo = aem.HardwareChangeInfo(netinfo)
        self.assertEquals(lastChange, hwChangeInfo.getLastHardwareChange())

        #Create mock hardware
        waagent.SetFileContents(testHwInfoFile, ("0\nma-ca-sa-ds-02"))
        hwChangeInfo = aem.HardwareChangeInfo(netinfo)
        self.assertNotEquals(None, hwChangeInfo.getLastHardwareChange())

        
    def test_linux_metric(self):
        config = self.test_config()
        metric = aem.LinuxMetric(config)
        self.validate_cnm_metric(metric)

    #Metric for CPU, network and memory
    def validate_cnm_metric(self, metric):
        self.assertNotEquals(None, metric.getCurrHwFrequency())
        self.assertNotEquals(None, metric.getMaxHwFrequency())
        self.assertNotEquals(None, metric.getCurrVMProcessingPower())
        self.assertNotEquals(None, metric.getGuaranteedMemAssigned())
        self.assertNotEquals(None, metric.getMaxVMProcessingPower())
        self.assertNotEquals(None, metric.getNumOfCoresPerCPU())
        self.assertNotEquals(None, metric.getNumOfThreadsPerCore())
        self.assertNotEquals(None, metric.getPhysProcessingPowerPerVCPU())
        self.assertNotEquals(None, metric.getProcessorType())
        self.assertNotEquals(None, metric.getReferenceComputeUnit())
        self.assertNotEquals(None, metric.getVCPUMapping())
        self.assertNotEquals(None, metric.getVMProcessingPowerConsumption())
        self.assertNotEquals(None, metric.getCurrMemAssigned())
        self.assertNotEquals(None, metric.getGuaranteedMemAssigned())
        self.assertNotEquals(None, metric.getMaxMemAssigned())
        self.assertNotEquals(None, metric.getVMMemConsumption())
        adapterIds = metric.getNetworkAdapterIds()
        self.assertNotEquals(None, adapterIds)
        self.assertNotEquals(0, len(adapterIds))
        adapterId = adapterIds[0]
        self.assertNotEquals(None, metric.getNetworkAdapterMapping(adapterId))
        self.assertNotEquals(None, metric.getMaxNetworkBandwidth(adapterId))
        self.assertNotEquals(None, metric.getMinNetworkBandwidth(adapterId))
        self.assertNotEquals(None, metric.getNetworkReadBytes())
        self.assertNotEquals(None, metric.getNetworkWriteBytes())
        self.assertNotEquals(None, metric.getNetworkPacketRetransmitted())
        self.assertNotEquals(None, metric.getLastHardwareChange())

    def test_vm_datasource(self):
        config = self.test_config()
        config.configData["lad.isenable"] = 0
        dataSource = aem.VMDataSource(config)
        counters = dataSource.collect()
        self.assertNotEquals(None, counters)
        self.assertNotEquals(0, len(counters))

        counterNames = [
            "Current Hw Frequency",
            "Current VM Processing Power",
            "Guaranteed VM Processing Power",
            "Max Hw Frequency",
            "Max. VM Processing Power",
            "Number of Cores per CPU",
            "Number of Threads per Core",
            "Phys. Processing Power per vCPU",
            "Processor Type",
            "Reference Compute Unit",
            "vCPU Mapping",
            "VM Processing Power Consumption",
            "Current Memory assigned",
            "Guaranteed Memory assigned",
            "Max Memory assigned",
            "VM Memory Consumption",
            "Adapter Id",
            "Mapping",
            "Maximum Network Bandwidth",
            "Minimum Network Bandwidth",
            "Network Read Bytes",
            "Network Write Bytes",
            "Packets Retransmitted"
        ]
        #print "\n".join(map(lambda c: str(c), counters))
        for name in counterNames:
            #print name
            counter = next((c for c in counters if c.name == name))
            self.assertNotEquals(None, counter)
            self.assertNotEquals(None, counter.value)

    def test_storagemetric(self):
        metrics = mock_getStorageMetrics()
        self.assertNotEquals(None, metrics)
        stat = aem.AzureStorageStat(metrics)
        self.assertNotEquals(None, stat.getReadBytes())
        self.assertNotEquals(None, stat.getReadOps())
        self.assertNotEquals(None, stat.getReadOpE2ELatency())
        self.assertNotEquals(None, stat.getReadOpServerLatency())
        self.assertNotEquals(None, stat.getReadOpThroughput())
        self.assertNotEquals(None, stat.getWriteBytes())
        self.assertNotEquals(None, stat.getWriteOps())
        self.assertNotEquals(None, stat.getWriteOpE2ELatency())
        self.assertNotEquals(None, stat.getWriteOpServerLatency())
        self.assertNotEquals(None, stat.getWriteOpThroughput())

    def test_disk_info(self):
        config = self.test_config()
        mapping = aem.DiskInfo(config).getDiskMapping()
        self.assertNotEquals(None, mapping)

    def test_get_storage_key_range(self):
        startKey, endKey = aem.getStorageTableKeyRange()
        self.assertNotEquals(None, startKey)
        self.assertEquals(13, len(startKey))
        self.assertNotEquals(None, endKey)
        self.assertEquals(13, len(endKey))

    def test_storage_datasource(self):
        aem.getStorageMetrics = mock_getStorageMetrics
        config = self.test_config()
        dataSource = aem.StorageDataSource(config)
        counters = dataSource.collect()

        self.assertNotEquals(None, counters)
        self.assertNotEquals(0, len(counters))

        counterNames = [
            "Phys. Disc to Storage Mapping",
            "Phys. Disc to Storage Mapping",
            "Storage ID",
            "Storage Read Bytes",
            "Storage Read Op Latency E2E msec",
            "Storage Read Op Latency Server msec",
            "Storage Read Ops",
            "Storage Read Throughput E2E MB/sec",
            "Storage Write Bytes",
            "Storage Write Op Latency E2E msec",
            "Storage Write Op Latency Server msec",
            "Storage Write Ops",
            "Storage Write Throughput E2E MB/sec"
        ]

        #print "\n".join(map(lambda c: str(c), counters))
        for name in counterNames:
            #print name
            counter = next((c for c in counters if c.name == name))
            self.assertNotEquals(None, counter)
            self.assertNotEquals(None, counter.value)

    def test_writer(self):
        testEventFile = "/tmp/Event"
        if os.path.isfile(testEventFile):
            os.remove(testEventFile)
        writer = aem.PerfCounterWriter()
        counters = [aem.PerfCounter(counterType = 0,
                                    category = "test",
                                    name = "test",
                                    value = "test",
                                    unit = "test")]

        writer.write(counters, eventFile = testEventFile)
        with open(testEventFile) as F:
            content = F.read()
            self.assertEquals(str(counters[0]), content)

        testEventFile = "/dev/console"
        print "=============================="
        print "The warning below is expected."
        self.assertRaises(IOError, writer.write, counters, 2, testEventFile)
        print "=============================="

    def test_parse_timestamp(self):
        date = aem.parseTimestamp("2015-01-15T03:39:01.2105360Z")
        self.assertEquals('1421264341', date)

    def test_get_ad_key_range(self):
        startKey, endKey = aem.getAzureDiagnosticKeyRange()
        self.assertEquals(60 * 1000 * 10000, endKey - startKey)

def mock_getStorageMetrics(*args, **kwargs):
        with open(os.path.join(env.test_dir, "storage_metrics")) as F:
            test_data = F.read()
        jsonObjs = json.loads(test_data)  
        class ObjectView(object):
            def __init__(self, data):
                self.__dict__ = data
        metrics = map(lambda x : ObjectView(x), jsonObjs)
        return metrics

if __name__ == '__main__':
    unittest.main()
