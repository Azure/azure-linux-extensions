#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation  
# All rights reserved.   
# MIT License  
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.  

from collections import defaultdict

class queryParameter:
    queryCondition = None
    def __init__(self):
        self.querySelectParameters = []
    def append(self, parameter):
        self.querySelectParameters.append(parameter)
    def getQuerySelectParameters(self):
        return self.querySelectParameters

# Currently we are using Counter names as \Processor\PercentProcessorTime in the metrics table. 
# In order to avoid confusion to users we would allow user to specify both the OMI accepted 
# class names as well as the class names used in performance counters in metrics table
classNameMapping = {
    'processor' : 'scx_processorstatisticalinformation',
    'memory' : 'scx_memorystatisticalinformation',
    'physicaldisk' : 'scx_diskdrivestatisticalinformation',
    'networkinterface' : 'scx_ethernetportstatistics',
}

# Checks for the mapping in classNameMapping, else checks if the class name is allowed class name, else throws exception
def getOmiClassName(name):
    if name.lower() in classNameMapping:
        name = classNameMapping[name.lower()]
    return name.lower()

# Generates OMI queries from omi query configurations
# Sample input
# {'LinuxCpu2': defaultdict({'root/scx':defaultdict({'scx_processorstatisticalinformation': {'queryCondition':'Name=/'_TOTAL/'','querySelectParameters':['PercentIOWaitTime']}})}),
# 'LinuxDisk': defaultdict({'root/scx':defaultdict({'scx_diskdrivestatisticalinformation': {'queryCondition':'Name=/'_TOTAL/'','querySelectParameters':['AverageWriteTime']}})}),
# 'LinuxCpu1': defaultdict({'root/scx':defaultdict({'scx_processorstatisticalinformation': {'queryCondition':None,'querySelectParameters':['PercentProcessorTime']}})})}
# Generated perfCfgList
# [{'query': "SELECT AverageWriteTime FROM scx_diskdrivestatisticalinformation WHERE Name='_TOTAL'", 'table': 'LinuxDisk'}, 
# {'query': "SELECT PercentIOWaitTime FROM scx_processorstatisticalinformation WHERE Name='_TOTAL'", 'table': 'LinuxCpu2'}, 
# {'query': 'SELECT PercentProcessorTime FROM scx_processorstatisticalinformation', 'table': 'LinuxCpu1'}]
def generateOMIQueries(omiQueryConfiguration):
    query = 'SELECT {0} FROM {1}'
    queryWithClause = 'SELECT {0} FROM {1} WHERE {2}'
    perfCfgList = []

    for tableName in omiQueryConfiguration.keys():
        for namespace in omiQueryConfiguration[tableName].keys():
            for className in omiQueryConfiguration[tableName][namespace].keys():
                queryParameters = omiQueryConfiguration[tableName][namespace][className]
                clause = queryParameters.queryCondition
                selectParameters = ''
                for counterName in queryParameters.getQuerySelectParameters():
                    selectParameters += counterName + ','
                if selectParameters:
                    perfCfg = dict()
                    perfCfg['table'] = tableName
                    if namespace != 'root/scx':
                        perfCfg['namespace'] = namespace
                    if clause:
                        perfCfg['query'] = queryWithClause.format(selectParameters[:-1], getOmiClassName(className), clause)
                    else:
                        perfCfg['query'] = query.format(selectParameters[:-1], getOmiClassName(className))
                perfCfgList.append(perfCfg)
    return perfCfgList

# Generates omi query configuration from the json config, required to generate the OMI queries
# We parse the configuration based on following rules
# Each table can contain counters from multiple class, 
# Each class within a table will correspond to 
# omi query and will have corresponding projection/select
# parameter and condition clause
# Sample performanceCounterConfiguration : "performanceCounters":{"performanceCounterConfiguration":[
# {"counterSpecifier":"PercentProcessorTime","class":"Processor","table":"LinuxCpu1"},
# {"counterSpecifier":"PercentIOWaitTime","class":"Processor","table":"LinuxCpu2","condition":"Name=\'_TOTAL\'"},
# {"counterSpecifier":"AverageWriteTime","class":"PhysicalDisk","table":"LinuxDisk","condition":"Name=\'_TOTAL\'"}]}}
# Generated omi configuration
# {'LinuxCpu2': defaultdict({'root/scx':defaultdict({'scx_processorstatisticalinformation': {'queryCondition':'Name=/'_TOTAL/'','querySelectParameters':['PercentIOWaitTime']}})}), 
# 'LinuxDisk': defaultdict({'root/scx':defaultdict({'scx_diskdrivestatisticalinformation': {'queryCondition':'Name=/'_TOTAL/'','querySelectParameters':['AverageWriteTime']}})}), 
# 'LinuxCpu1': defaultdict({'root/scx':defaultdict({'scx_processorstatisticalinformation': {'queryCondition':None,'querySelectParameters':['PercentProcessorTime']}})})}
def generateOmiQueryConfiguration(performanceCounterConfiguration):
    omiQueryConfiguration = defaultdict(defaultdict)
    for performanceCounter in performanceCounterConfiguration['performanceCounterConfiguration']:
        if 'table' not in performanceCounter or 'counterSpecifier' not in performanceCounter or 'class' not in performanceCounter:
            raise Exception("Incomplete performance counter configuration")
        className = getOmiClassName(performanceCounter['class'])
        tableName = performanceCounter['table']
        if 'condition' in performanceCounter:
            condition = performanceCounter['condition']
        else:
            condition = None
        if 'namespace' in performanceCounter:
            namespace = performanceCounter['namespace']
        else:
            namespace = 'root/scx'
        if not tableName in omiQueryConfiguration:
            omiQueryConfiguration[tableName] = defaultdict(defaultdict)
        if not namespace in omiQueryConfiguration[tableName]:
            omiQueryConfiguration[tableName][namespace] = defaultdict(queryParameter)
        if not className in omiQueryConfiguration[tableName][namespace]:
            omiQueryConfiguration[tableName][namespace][className] = queryParameter()
            omiQueryConfiguration[tableName][namespace][className].queryCondition = condition
        else:
            if omiQueryConfiguration[tableName][namespace][className].queryCondition != condition:
                raise Exception('Cannot have two different conditions on same table')
        if not performanceCounter['counterSpecifier'] in omiQueryConfiguration[tableName][namespace][className].querySelectParameters:
            omiQueryConfiguration[tableName][namespace][className].append(performanceCounter['counterSpecifier'])
    return omiQueryConfiguration

# Get elements from DiagnosticsMonitorConfiguration in LadCfg based on element name
def getDiagnosticsMonitorConfigurationElement(ladCfg, elementName):
    if ladCfg:
        if 'diagnosticMonitorConfiguration' in ladCfg:
            if elementName in ladCfg['diagnosticMonitorConfiguration']:
                return ladCfg['diagnosticMonitorConfiguration'][elementName]

# Get fileCfg form FileLogs in LadCfg
def getFileCfgFromLadCfg(ladCfg):
    fileLogs = getDiagnosticsMonitorConfigurationElement(ladCfg, 'fileLogs')
    if fileLogs:
        if 'fileLogConfiguration' in fileLogs:
            return fileLogs['fileLogConfiguration']

# Generates OMI queries from LadCfg
def generatePerformanceCounterConfigurationFromLadCfg(ladCfg):
    performanceCounters = getDiagnosticsMonitorConfigurationElement(ladCfg, 'performanceCounters')
    if performanceCounters:
        omiQueryConfiguration = generateOmiQueryConfiguration(performanceCounters)
        return generateOMIQueries(omiQueryConfiguration)

# Get resource Id from LadCfg
def getResourceIdFromLadCfg(ladCfg):
    metricsConfiguration = getDiagnosticsMonitorConfigurationElement(ladCfg, 'metrics')
    if metricsConfiguration:
        if 'resourceId' in metricsConfiguration:
            return metricsConfiguration['resourceId']

# Get event volume from LadCfg
def getEventVolumeFromLadCfg(ladCfg):
    return getDiagnosticsMonitorConfigurationElement(ladCfg, 'eventVolume')

