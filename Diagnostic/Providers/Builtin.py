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
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
#  the Software.
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
import xml.etree.ElementTree as ET
import Utils.XmlUtil as XmlUtil
from xml.sax.saxutils import quoteattr


# These are the built-in metrics this code provides, grouped by class. The builtin countername space is
# case insensitive; this collection of maps converts to the case-sensitive OMI name.
_builtIns = {
    'processor':  { 'percentidletime': 'PercentIdleTime', 'percentprocessortime': 'PercentProcessorTime',
                    'percentiowaittime': 'PercentIOWaitTime', 'percentinterrupttime': 'PercentInterruptTime',
                    'percentusertime': 'PercentUserTime', 'percentnicetime': 'PercentNiceTime',
                    'percentprivilegedtime': 'PercentPrivilegedTime' },
    'memory':     { 'availablememory': 'AvailableMemory', 'percentavailablememory': 'PercentAvailableMemory',
                    'usedmemory': 'UsedMemory', 'percentusedmemory': 'PercentUsedMemory',
                    'pagespersec': 'PagesPerSec', 'pagesreadpersec': 'PagesReadPerSec',
                    'pageswrittenpersec': 'PagesWrittenPerSec', 'availableswap': 'AvailableSwap',
                    'percentavailableswap': 'PercentAvailableSwap', 'usedswap': 'UsedSwap',
                    'percentusedswap': 'PercentUsedSwap'},
    'network':    { 'bytestransmitted': 'BytesTransmitted', 'bytesreceived': 'BytesReceived',
                    'bytestotal': 'BytesTotal', 'packetstransmitted': 'PacketsTransmitted',
                    'packetsreceived': 'PacketsReceived', 'totalrxerrors': 'TotalRxErrors',
                    'totaltxerrors': 'TotalTxErrors', 'totalcollisions': 'TotalCollisions' },
    'filesystem': { 'freespace': 'FreeMegabytes', 'usedspace': 'UsedMegabytes',
                    'percentfreespace': 'PercentFreeSpace', 'percentusedspace': 'PercentUsedSpace',
                    'percentfreeinodes': 'PercentFreeInodes', 'percentusedinodes': 'PercentUsedInodes',
                    'bytesreadpersecond': 'ReadBytesPerSecond', 'byteswrittenpersecond': 'WriteBytesPerSecond',
                    'bytespersecond': 'BytesPerSecond', 'readspersecond': 'ReadsPerSecond',
                    'writespersecond': 'WritesPerSecond', 'transferspersecond': 'TransfersPerSecond' },
    'disk':       { 'readspersecond': 'ReadsPerSecond', 'writespersecond': 'WritesPerSecond',
                    'transferspersecond': 'TransfersPerSecond', 'averagereadtime': 'AverageReadTime',
                    'averagewritetime': 'AverageWriteTime', 'averagetransfertime': 'AverageTransferTime',
                    'averagediskqueuelength': 'AverageDiskQueueLength', 'readbytespersecond': 'ReadBytesPerSecond',
                    'writebytespersecond': 'WriteBytesPerSecond', 'bytespersecond': 'BytesPerSecond' }
    }

_omiClassName = { 'processor': 'SCX_ProcessorStatisticalInformation',
                  'memory': 'SCX_MemoryStatisticalInformation',
                  'network': 'SCX_EthernetPortStatistics',
                  'filesystem': 'SCX_FileSystemStatisticalInformation',
                  'disk': 'SCX_DiskDriveStatisticalInformation'
                }

# Default CQL condition clause (WHERE ...) for relevant counter classes
_defaultCqlCondition = {
                        #'network': '...',  # No 'Name' or 'IsAggregate' columns from SCX_EthernetPort... cql query.
                                            # If there are multiple NICs, this might cause some issue. Beware.
                                            # The column/value distinguishing NICs is e.g., 'InstanceID="eth0"'.
                        'filesystem': 'IsAggregate=TRUE',  # For specific file system (e.g., root fs), use 'Name="/"'
                        'disk': 'IsAggregate=TRUE',  # For specific disk (e.g., /dev/sda), use 'Name="sda"'
                        'processor': 'IsAggregate=TRUE',  # For specific processor core, use 'Name="0"'
                        #'memory': 'IsAggregate=TRUE',  # No separate instances of memory, so no WHERE condition is needed
                       }

# The Azure Metrics infrastructure, along with App Insights, requires that quantities be measured
# in one of these units: Percent, Count, Seconds, Milliseconds, Bytes, BytesPerSecond, CountPerSecond
#
# Some of the OMI metrics are retrieved in some other unit (e.g. "MiB") and need to be scaled
# to the expected unit before being passed along the pipeline. The _scaling map holds all OMI counter
# names that need to be scaled. If a counterSpecifier isn't in this list, no scaling is needed.
_scaling = defaultdict(lambda:defaultdict(str),
            { 'memory' : defaultdict(str,
                { 'AvailableMemory': 'scaleUp="1048576"',
                  'UsedMemory': 'scaleUp="1048576"',
                  'AvailableSwap': 'scaleUp="1048576"',
                  'UsedSwap': 'scaleUp="1048576"'
                } ),
              'filesystem' : defaultdict(str,
                 {'FreeMegabytes': 'scaleUp="1048576"',
                  'UsedMegabytes': 'scaleUp="1048576"',
                  }),
              } )

_metrics = defaultdict(list)
_eventNames = {}

_defaultSampleRate = 15


def SetDefaultSampleRate(rate):
    global _defaultSampleRate
    _defaultSampleRate = rate


def default_condition(class_name):
    return _defaultCqlCondition[class_name] if class_name in _defaultCqlCondition else ''


class BuiltinMetric:
    def __init__(self, counterSpec):
        """
        Construct an instance of the BuiltinMetric class. Values are case-insensitive unless otherwise noted.

        "type": the provider type. If present, must have value "builtin". If absent, assumed to be "builtin".
        "class": the name of the class within which this metric is scoped. Must be a key in the _builtIns dict.
        "counter": the name of the metric, within the class. Must appear in the list of metric names for this class
                found in the _builtIns dict. In this implementation, the builtin counter name is mapped to the OMI
                counter name
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

        self._CounterClass = ProvUtil.GetCounterSetting(counterSpec, 'class')
        if self._CounterClass is None:
            raise ProvUtil.InvalidCounterSpecification('Builtin metric spec missing "class"')
        self._CounterClass = self._CounterClass.lower()
        if self._CounterClass not in _builtIns:
            raise ProvUtil.InvalidCounterSpecification('Unknown Builtin class {0}'.format(self._CounterClass))
        builtin_raw_counter_name = ProvUtil.GetCounterSetting(counterSpec, 'counter')
        if builtin_raw_counter_name is None:
            raise ProvUtil.InvalidCounterSpecification('Builtin metric spec missing "counter"')
        builtin_counter_name = builtin_raw_counter_name.lower()
        if builtin_counter_name not in _builtIns[self._CounterClass]:
            raise ProvUtil.InvalidCounterSpecification(
                'Counter {0} not in builtin class {1}'.format(builtin_raw_counter_name, self._CounterClass))
        self._Counter = _builtIns[self._CounterClass][builtin_counter_name]
        self._Condition = ProvUtil.GetCounterSetting(counterSpec, 'condition')
        self._Label = ProvUtil.GetCounterSetting(counterSpec, 'counterSpecifier')
        if self._Label is None:
            raise ProvUtil.InvalidCounterSpecification(
                'No counterSpecifier set for builtin {1} {0}'.format(self._Counter, self._CounterClass))
        self._SampleRate = ProvUtil.GetCounterSetting(counterSpec, 'sampleRate')

    def is_type(self, t):
        """
        Returns True if the metric is of the specified type.
        :param t: The name of the metric type to be checked
        :return bool:
        """
        return self._Type == t.lower()

    def class_name(self):
        return self._CounterClass

    def counter_name(self):
        return self._Counter

    def condition(self):
        return self._Condition

    def label(self):
        return self._Label

    def sample_rate(self):
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
    :return: the generated local-table name in mdsd into which this metric will be fetched, or None
    """
    global _metrics, _eventNames
    try:
        metric = BuiltinMetric(counter_spec)
    except ProvUtil.ParseException as ex:
        print "Couldn't create metric: ", ex
        return None

    # (class, instanceId, sampleRate) -> [ metric ]
    # Given a class, instance within that class, and sample rate, we have a list of the requested metrics
    # matching those constraints. For that set of constraints, we also have a common eventName, the local
    # table where we store the collected metrics.

    key = (metric.class_name(), metric.condition(), metric.sample_rate())
    if key not in _eventNames:
        _eventNames[key] = ProvUtil.MakeUniqueEventName('builtin')
    _metrics[key].append(metric)
    return _eventNames[key]


def UpdateXML(doc):
    """
    Add to the mdsd XML the minimal set of OMI queries which will retrieve the metrics requested via AddMetric(). This
    provider doesn't need any configuration external to mdsd; if it did, that would be generated here as well.

    :param doc: XML document object to be updated
    :return: None
    """
    global _metrics, _eventNames, _omiClassName
    for group in _metrics:
        (class_name, condition_clause, sample_rate) = group
        if not condition_clause:
            condition_clause = default_condition(class_name)
        columns = []
        mappings = []
        for metric in _metrics[group]:
            omi_name = metric.counter_name()
            scale = _scaling[class_name][omi_name]
            columns.append(omi_name)
            mappings.append('<MapName name="{0}" {1}>{2}</MapName>'.format(omi_name, scale, metric.label()))
        column_string = ','.join(columns)
        if condition_clause:
            cql_query = quoteattr("SELECT {0} FROM {1} WHERE {2}".format(column_string,
                                                                         _omiClassName[class_name], condition_clause))
        else:
            cql_query = quoteattr("SELECT {0} FROM {1}".format(column_string, _omiClassName[class_name]))
        query = '''
<OMIQuery cqlQuery={qry} eventName={evname} omiNamespace="root/scx" sampleRateInSeconds="{rate}" storeType="local">
  <Unpivot columnName="CounterName" columnValue="Value" columns={columns}>
    {mappings}
  </Unpivot>
</OMIQuery>'''.format(
            qry=cql_query,
            evname=quoteattr(_eventNames[group]),
            columns=quoteattr(column_string),
            rate=sample_rate,
            mappings='\n    '.join(mappings)
        )
        XmlUtil.addElement(doc, 'Events/OMI', ET.fromstring(query))
    return
