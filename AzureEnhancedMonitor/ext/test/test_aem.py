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

import datetime
import os
import json
import unittest

import env
import aem
from Utils.WAAgentUtil import waagent

TestPublicConfig = """\
{
    "cfg": [{
        "key":  "vmsize",
        "value":  "Small (A1)"
    },{
        "key":  "vm.roleinstance",
        "value":  "osupdate"
    },{
        "key":  "vm.role",
        "value":  "IaaS"
    },{
        "key":  "vm.deploymentid",
        "value":  "cd98461b43364478a908d03d0c3135a7"
    },{
        "key":  "vm.memory.isovercommitted",
        "value":  0
    },{
        "key":  "vm.cpu.isovercommitted",
        "value":  0
    },{
        "key":  "script.version",
        "value":  "1.2.0.0"
    },{
        "key":  "verbose",
        "value":  "0"
    },{
        "key":  "osdisk.connminute",
        "value":  "asdf.minute"
    },{
        "key":  "osdisk.connhour",
        "value":  "asdf.hour"
    },{
        "key":  "osdisk.name",
        "value":  "osupdate-osupdate-2015-02-12.vhd"
    },{
        "key":  "asdf.hour.uri",
        "value":  "https://asdf.table.core.windows.net/$metricshourprimarytransactionsblob"
    },{
        "key":  "asdf.minute.uri",
        "value":  "https://asdf.table.core.windows.net/$metricsminuteprimarytransactionsblob"
    },{
        "key":  "asdf.hour.name",
        "value":  "asdf"
    },{
        "key":  "asdf.minute.name",
        "value":  "asdf"
    },{
        "key":  "wad.name",
        "value":  "asdf"
    },{
        "key":  "wad.isenabled",
        "value":  "1"
    },{
        "key":  "wad.uri",
        "value":  "https://asdf.table.core.windows.net/wadperformancecounterstable"
    }]
}
"""
TestPrivateConfig = """\
{
    "cfg" : [{
        "key" : "asdf.minute.key",
        "value" : "qwer"
    },{
        "key" : "wad.key",
        "value" : "qwer"
    }]
}
"""
class TestAEM(unittest.TestCase):
    def setUp(self):
        waagent.LoggerInit("/dev/null", "/dev/stdout")

    def test_config(self):
        publicConfig = json.loads(TestPublicConfig)
        privateConfig = json.loads(TestPrivateConfig)
        config = aem.EnhancedMonitorConfig(publicConfig, privateConfig)
        self.assertNotEquals(None, config)
        self.assertEquals(".table.core.windows.net", 
                          config.getStorageHostBase('asdf'))
        self.assertEquals(".table.core.windows.net", 
                          config.getLADHostBase())
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
        self.assertNotEquals(None, counter.value)

        name = "Virtualization Solution"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertNotEquals(None, counter.value)

        name = "Instance Type"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("Small (A1)", counter.value)

        name = "Data Sources"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("wad", counter.value)

        name = "Data Provider Version"
        counter = next((c for c in counters if c.name == name))
        self.assertNotEquals(None, counter)
        self.assertEquals("2.0.0", counter.value)

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
        self.assertNotEquals(0, cpuinfo.getNumOfCoresPerCPU())
        self.assertNotEquals(0, cpuinfo.getNumOfCores())
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
        config.configData["wad.isenabled"] = "0"
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
        print("==============================")
        print("The warning below is expected.")
        self.assertRaises(IOError, writer.write, counters, 2, testEventFile)
        print("==============================")

    def test_easyHash(self):
        hashVal = aem.easyHash('a')
        self.assertEquals(97, hashVal)
        hashVal = aem.easyHash('ab')
        self.assertEquals(87, hashVal)
        hashVal = aem.easyHash(("ciextension-SUSELinuxEnterpriseServer11SP3"
                                "___role1___"
                                "ciextension-SUSELinuxEnterpriseServer11SP3"))
        self.assertEquals(5, hashVal)
    
    def test_get_ad_key_range(self):
        startKey, endKey = aem.getAzureDiagnosticKeyRange()
        print(startKey)
        print(endKey)

    def test_get_mds_timestamp(self):
        date = datetime.datetime(2015, 1, 26, 3, 54)
        epoch = datetime.datetime.utcfromtimestamp(0)
        unixTimestamp = (int((date - epoch).total_seconds()))
        mdsTimestamp = aem.getMDSTimestamp(unixTimestamp)
        self.assertEquals(635578412400000000, mdsTimestamp)
    
    def test_get_storage_timestamp(self):
        date = datetime.datetime(2015, 1, 26, 3, 54)
        epoch = datetime.datetime.utcfromtimestamp(0)
        unixTimestamp = (int((date - epoch).total_seconds()))
        storageTimestamp = aem.getStorageTimestamp(unixTimestamp)
        self.assertEquals("20150126T0354", storageTimestamp)

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
