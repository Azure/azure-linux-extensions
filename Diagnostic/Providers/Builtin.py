#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# A provider is responsible for taking a particular syntax of configuration instructions, as found in the JSON config
# blob, and using it to enable collection of data as specified in those instructions.

# The "Builtin" configuration instructions are agnostic to the collection mechanism used to implement them; it's simply
# a list of metrics to be collected on a particular schedule. The metric names are collected into classes for ease
# of understanding by the user. The predefined classes and metric names are available without regard to how the
# underlying mechanism might name them.
#
# This specific implementation of the Builtin provider converts the configuration instructions into a set of OMI
# queries to be executed by the mdsd agent. The agent executes the queries are written by this provider and uploads
# the results to the appropriate table in the customer's storage account.
#
# A different implementation might use fluentd to collect the data and to upload the results to table storage.

# A different provider (e.g. an OMI provider) would expect configuration instructions bound directly to OMI; that is,
# the PublicConfig JSON delivered to LAD would itself contain actual OMI queries. The implementation of such a provider
# might construct an mdsd configuration file cause mdsd to run the specified queries and store the data in tables.

import Utils.ProviderUtil as ProvUtil
from collections import defaultdict

# These are the built-in metrics this code provides, grouped by class.
_builtIns = {
    'processor':  [ 'percentidletime', 'percentprocessortime', 'percentiowaittime', 'percentinterrupttime',
                    'percentusertime', 'percentnicetime', 'percentprivilegedtime' ],
    'memory':     [ 'availablememory', 'percentavailablememory', 'usedmemory', 'percentusedmemory', 'pagespersec',
                    'pagesreadpersec', 'pageswrittenpersec', 'availableswap', 'percentavailableswap', 'usedswap',
                    'percentusedswap' ],
    'network':    [ 'bytestransmitted', 'bytesreceived', 'bytestotal', 'packetstransmitted', 'packetsreceived',
                    'totalrxerrors', 'totaltxerrors', 'totalcollisions' ],
    'filesystem': [ 'freemegabytes', 'usedmegabytes', 'percentfreespace', 'percentusedspace', 'percentfreeinodes',
                    'percentusedinodes', 'bytesreadpersecond', 'byteswrittenpersecond', 'bytespersecond',
                    'readspersecond', 'writespersecond', 'transferspersecond' ],
    'disk':       [ 'readspersecond', 'writespersecond', 'transferspersecond', 'averagereadtime', 'averagewritetime',
                    'averagetransfertime', 'averagediskqueuelength', 'readbytespersecond', 'writebytespersecond',
                    'bytespersecond' ]
    }

_omiClassName = { 'processor': 'SCX_ProcessorStatisticalInformation',
                  'memory': 'SCX_MemoryStatisticalInformation',
                  'network': 'SCX_EthernetPortStatistics',
                  'filesystem': 'SCX_FileSystemStatisticalInformation',
                  'disk': 'SCX_DiskDriveStatisticalInformation'
                }

# There can be multiple NICs, multiple drives and filesystems, multiple cores... only one pile of memory.
_instancedClasses = ['network', 'filesystem', 'disk', 'processor']

# The Azure Metrics infrastructure, along with App Insights, requires that quantities be measured
# in one of these units: Percent, Count, Seconds, Milliseconds, Bytes, BytesPerSecond, CountPerSecond
#
# Some of the built-in metrics are retrieved in some other unit (e.g. "MiB") and need to be scaled
# to the expected unit before being passed along the pipeline. The _scaling map holds all counterSpecifier
# names that need to be scaled. If a counterSpecifier isn't in this list, no scaling is needed.
_scaling = defaultdict(lambda:defaultdict(str),
            { 'memory' : defaultdict(str,
                { 'availablememory': 'scaleUp="1048576"',
                  'usedmemory': 'scaleUp="1048576"',
                  'availableswap': 'scaleUp="1048576"',
                  'usedswap': 'scaleUp="1048576"'
                } )
            } )

_metrics = defaultdict(list)
_eventNames = {}

_defaultSampleRate = 15

def SetDefaultSampleRate(rate):
    global _defaultSampleRate
    _defaultSampleRate = rate

class BuiltinMetric:
    def __init__(self, counterSpec):
        """
        Construct an instance of the BuiltinMetric class. Values are case-insensitive unless otherwise noted.

        "type": the provider type. If present, must have value "builtin". If absent, assumed to be "builtin".
        "class": the name of the class within which this metric is scoped. Must be a key in the _builtIns dict.
        "counter": the name of the metric, within the class. Must appear in the list of metric names for this class
                found in the _builtIns dict.
        "instanceId": the identifier for the specific instance of the metric, if any. Must be "None" for uninstanced
                metrics.
        "counterSpecifier": the name under which this retrieved metric will be stored
        "sampleRate": a string containing an ISO8601-compliant duration.

        :param counterSpec: A dict containing the key/value settings that define the metric to be collected.
        """
        t = ProvUtil.GetCounterSetting(counterSpec, 'type')
        if t is None:
            self._Type = 'builtin'
        else:
            self._Type = t.lower()
            if t != 'builtin':
                raise ProvUtil.UnexpectedCounterType('Expected type "builtin" but saw type "{0}"'.format(self._Type))

        self._CounterClass = ProvUtil.GetCounterSetting(counterSpec, 'class').lower()
        if self._CounterClass not in _builtIns:
            raise ProvUtil.InvalidCounterSpecification('Unknown Builtin class {0}'.format(self._CounterClass))
        self._Counter = ProvUtil.GetCounterSetting(counterSpec, 'counter').lower()
        if self._Counter not in _builtIns[self._CounterClass]:
            raise ProvUtil.InvalidCounterSpecification(
                'Counter {0} not in builtin class {1}'.format(self._Counter, self._CounterClass))
        self._InstanceId = ProvUtil.GetCounterSetting(counterSpec, 'instanceId')
        self._Label = ProvUtil.GetCounterSetting(counterSpec, 'counterSpecifier')
        self._SampleRate = ProvUtil.GetCounterSetting(counterSpec, 'sampleRate')

    def IsType(self, t):
        """
        Returns True if the metric is of the specified type.
        :param t: The name of the metric type to be checked
        :return bool:
        """
        return self._Type == t.lower()

    def Class(self):
        return self._CounterClass

    def Counter(self):
        return self._Counter

    def InstanceId(self):
        return self._InstanceId

    def Label(self):
        return self._Label

    def SampleRate(self):
        """
        Determine how often this metric should be retrieved. If the metric didn't define a sample period, return the
        default.
        :return int: Number of seconds between collecting samples of this metric.
        """
        if self._SampleRate is None:
            return _defaultSampleRate
        else:
            return ProvUtil.IntervalToSeconds(self._SampleRate)


def AddMetric(counter_spec):
    """
    Add a metric to the list of metrics to be collected.
    :param counter_spec: The specification of a builtin metric.
    """
    global _metrics, _eventNames
    try:
        metric = BuiltinMetric(counter_spec)
    except ProvUtil.ParseException as ex:
        print "Couldn't create metric: ", ex
        return

    # (class, instanceId, sampleRate) -> [ metric ]
    # Given a class, instance within that class, and sample rate, we have a list of the requested metrics
    # matching those constraints. For that set of constraints, we also have a common eventName, the local
    # table where we store the collected metrics.

    key = (metric.Class(), metric.InstanceId(), metric.SampleRate() )
    if key not in _eventNames:
        _eventNames[key] = ProvUtil.MakeUniqueEventName('builtin')
    _metrics[key].append(metric)


def GenerateOMIQuery():
    """
    Build the minimal set of OMI queries which will retrieve the metrics requested via AddMetric().
    :return: A string containing an XML mdsd configuration of OMI queries to collect the raw metrics on schedule.
    """
    global _metrics, _eventNames, _omiClassName
    queries = []
    for group in _metrics:
        (class_name, instance_id, sample_rate) = group
        if class_name in _instancedClasses and not instance_id:
            instance_id = '_Total'
        columns = []
        mappings = []
        for metric in _metrics[group]:
            columns.append(metric.Counter())
            mappings.append('<MapName name="{0}">{1}</MapName>'.format(metric.Counter(), metric.Label()))
        column_string = ','.join(columns)
        if instance_id:
            where_clause = " WHERE name='{0}'".format(instance_id)
        else:
            where_clause = ""
        queries.append('''
<OMIQuery cqlQuery="SELECT {0} FROM {1}{2}" eventName="{3}" omiNamespace="root/scx" sampleRateInSeconds="{4}" storeType="local">
  <Unpivot columnName="CounterName" columnValue="Value" columns="{0}">
    {5}
  </Unpivot>
</OMIQuery>'''.format(
            column_string,
            _omiClassName[class_name],
            where_clause,
            _eventNames[group],
            sample_rate,
            '\n    '.join(mappings)
        ))
    return ''.join(queries)


#import base64
#import datetime
#import os
#import os.path
#import platform
#import re
#import signal
#import string
#import subprocess
#import sys
#import syslog
#import time
#import traceback
#import xml.dom.minidom
#import xml.etree.ElementTree as ET
#
#import Utils.HandlerUtil as Util
#import Utils.LadDiagnosticUtil as LadUtil
#import Utils.XmlUtil as XmlUtil
#import Utils.ApplicationInsightsUtil as AIUtil
#from Utils.WAAgentUtil import waagent
