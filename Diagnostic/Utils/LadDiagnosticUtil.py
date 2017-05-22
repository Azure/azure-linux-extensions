#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation  
# All rights reserved.   
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above
# copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software. THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
#  CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


# Get elements from DiagnosticsMonitorConfiguration in LadCfg based on element name
def getDiagnosticsMonitorConfigurationElement(ladCfg, elementName):
    if ladCfg and 'diagnosticMonitorConfiguration' in ladCfg:
        if elementName in ladCfg['diagnosticMonitorConfiguration']:
            return ladCfg['diagnosticMonitorConfiguration'][elementName]
    return None


# Get fileCfg form FileLogs in LadCfg
def getFileCfgFromLadCfg(ladCfg):
    fileLogs = getDiagnosticsMonitorConfigurationElement(ladCfg, 'fileLogs')
    if fileLogs and 'fileLogConfiguration' in fileLogs:
        return fileLogs['fileLogConfiguration']
    return None


# Get resource Id from LadCfg
def getResourceIdFromLadCfg(ladCfg):
    metricsConfiguration = getDiagnosticsMonitorConfigurationElement(ladCfg, 'metrics')
    if metricsConfiguration and 'resourceId' in metricsConfiguration:
        return metricsConfiguration['resourceId']
    return None


# Get event volume from LadCfg
def getEventVolumeFromLadCfg(ladCfg):
    return getDiagnosticsMonitorConfigurationElement(ladCfg, 'eventVolume')


# Get default sample rate from LadCfg
def getDefaultSampleRateFromLadCfg(ladCfg):
    if ladCfg and 'sampleRateInSeconds' in ladCfg:
        return ladCfg['sampleRateInSeconds']
    return None


def getPerformanceCounterCfgFromLadCfg(ladCfg):
    """
    Return the array of metric definitions
    :param ladCfg:
    :return: array of metric definitions
    """
    performanceCounters = getDiagnosticsMonitorConfigurationElement(ladCfg, 'performanceCounters')
    if performanceCounters and 'performanceCounterConfiguration' in performanceCounters:
        return performanceCounters['performanceCounterConfiguration']
    return None


def getAggregationPeriodsFromLadCfg(ladCfg):
    """
    Return an array of aggregation periods as specified. If nothing appears in the config, default PT1H
    :param ladCfg:
    :return: array of ISO 8601 intervals
    :rtype: List(str)
    """
    results = []
    metrics = getDiagnosticsMonitorConfigurationElement(ladCfg, 'metrics')
    if metrics and 'metricAggregation' in metrics:
        for item in metrics['metricAggregation']:
            if 'scheduledTransferPeriod' in item:
                # assert isinstance(item['scheduledTransferPeriod'], str)
                results.append(item['scheduledTransferPeriod'])
    else:
        results.append('PT1H')
    return results


def getSinkList(feature_config):
    """
    Returns the list of sink names to which all data should be forwarded, according to this config
    :param feature_config: The JSON config for a feature (e.g. the struct for "performanceCounters" or "syslogEvents")
    :return: the list of names; might be an empty list
    :rtype: [str]
    """
    if feature_config and 'sinks' in feature_config and feature_config['sinks']:
        return [sink_name.strip() for sink_name in feature_config['sinks'].split(',')]
    return []


def getFeatureWideSinksFromLadCfg(ladCfg, feature_name):
    """
    Returns the list of sink names to which all data for the given feature should be forwarded
    :param ladCfg: The ladCfg JSON config
    :param str feature_name: Name of the feature. Expected to be "performanceCounters" or "syslogEvents"
    :return: the list of names; might be an empty list
    :rtype: [str]
    """
    return getSinkList(getDiagnosticsMonitorConfigurationElement(ladCfg, feature_name))


class SinkConfiguration:
    def __init__(self):
        self._sinks = {}

    def insert_from_config(self, json):
        """
        Walk through the sinksConfig JSON object and add all sinks within it. Every accepted sink is guaranteed to
        have a 'name' and 'type' element.
        :param json: A hash holding the body of a sinksConfig object
        :return: A string containing warning messages, or an empty string
        """
        msgs = []
        if json and 'sink' in json:
            for sink in json['sink']:
                if 'name' in sink and 'type' in sink:
                    self._sinks[sink['name']] = sink
                else:
                    msgs.append('Ignoring invalid sink definition {0}'.format(sink))
        return '\n'.join(msgs)

    def get_sink_by_name(self, sink_name):
        """
        Return the JSON object defining a particular sink.
        :param sink_name: string name of sink
        :return: JSON object or None
        """
        if sink_name in self._sinks:
            return self._sinks[sink_name]
        return None

    def get_all_sink_names(self):
        """
        Return a list of all names of defined sinks.
        :return: list of names
        """
        return self._sinks.keys()

    def get_sinks_by_type(self, sink_type):
        """
        Return a list of all names of defined sinks.
        :return: list of names
        """
        return [self._sinks[name] for name in self._sinks if self._sinks[name]['type'] == sink_type]
