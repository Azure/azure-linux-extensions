#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import unittest
import Utils.LadDiagnosticUtil as LadUtil


class TestGetDiagnosticsMonitorConfigurationElement(unittest.TestCase):
    def setUp(self):
        self.empty_config = {}
        self.bogus_config = {"foo": "bar"}
        self.missing_from_config = {"diagnosticMonitorConfiguration": {"foo": "bar"}}
        self.valid_config = \
            {
                "diagnosticMonitorConfiguration":
                    {
                        "foo": "bar",
                        "eventVolume": "Large",
                        "sinksConfig": {
                            "Sink": [
                                {
                                    "name": "sink1",
                                    "type": "EventHub",
                                    "sasURL": "https://sbnamespace.servicebus.windows.net/raw?sr=https%3a%2f%2fsb"
                                              "namespace.servicebus.windows.net%2fraw%2f&sig=SIGNATURE%3d"
                                              "&se=1804371161&skn=writer"
                                }
                            ]
                        },
                        "metrics": {
                            "resourceId": "/subscriptions/1111-2222-3333-4444/resourcegroups/RG1/compute/foo",
                            "metricAggregation": [
                                {"scheduledTransferPeriod": "PT5M"},
                                {"scheduledTransferPeriod": "PT1H"},
                            ]
                        },
                        "performanceCounters": {
                            "sinks": "sink1",
                            "performanceCounterConfiguration": [
                                {
                                    "type": "builtin",
                                    "class": "Processor",
                                    "counter": "PercentIdleTime",
                                    "counterSpecifier": "/builtin/Processor/PercentIdleTime",
                                    "condition": "IsAggregate=TRUE",
                                    "sampleRate": "PT15S",
                                    "unit": "Percent",
                                    "annotation": [
                                        {
                                            "displayName": "Aggregate CPU %idle time",
                                            "locale": "en-us"
                                        }
                                    ]
                                }
                            ]
                        },
                        "syslogEvents": {
                            "sinks": "sink2",
                            "syslogEventConfiguration": {
                                "LOG_LOCAL1": "LOG_INFO",
                                "LOG_MAIL": "LOG_FATAL"
                            }
                        }
                    },
                "sampleRateInSeconds": 60
            }

    def test_empty_config(self):
        self.assertIsNone(LadUtil.getDiagnosticsMonitorConfigurationElement(self.empty_config, "dummy"))

    def test_bogus_config(self):
        self.assertIsNone(LadUtil.getDiagnosticsMonitorConfigurationElement(self.bogus_config, "dummy"))

    def test_entry_not_present(self):
        self.assertIsNone(LadUtil.getDiagnosticsMonitorConfigurationElement(self.missing_from_config, "dummy"))

    def test_entry_is_present(self):
        self.assertEqual(LadUtil.getDiagnosticsMonitorConfigurationElement(self.valid_config, "foo"), "bar")

    def test_getDefaultSampleRateFromLadCfg(self):
        self.assertEqual(LadUtil.getDefaultSampleRateFromLadCfg(self.valid_config), 60)

    def test_getEventVolumeFromLadCfg(self):
        self.assertEqual(LadUtil.getEventVolumeFromLadCfg(self.valid_config), "Large")

    def test_getAggregationPeriodsFromLadCfg(self):
        periods = LadUtil.getAggregationPeriodsFromLadCfg(self.valid_config)
        self.assertEqual(len(periods), 2)
        self.assertIn('PT5M', periods)
        self.assertIn('PT1H', periods)

    def test_getPerformanceCounterCfgFromLadCfg(self):
        definitions = LadUtil.getPerformanceCounterCfgFromLadCfg(self.valid_config)
        self.assertEqual(1, len(definitions))
        metric = definitions[0]
        self.assertIn('counterSpecifier', metric)
        self.assertEqual('/builtin/Processor/PercentIdleTime', metric['counterSpecifier'])

    def test_getResourceIdFromLadCfg(self):
        self.assertIsNone(LadUtil.getResourceIdFromLadCfg(self.missing_from_config))
        res_id = LadUtil.getResourceIdFromLadCfg(self.valid_config)
        self.assertIsNotNone(res_id)
        self.assertIn("1111-2222-3333-4444", res_id)

    def test_getFeatureWideSinksFromLadCfg(self):
        self.assertEqual(LadUtil.getFeatureWideSinksFromLadCfg(self.valid_config, 'syslogEvents'), ['sink2'])
        self.assertEqual(LadUtil.getFeatureWideSinksFromLadCfg(self.valid_config, 'performanceCounters'), ['sink1'])


class TestSinkConfiguration(unittest.TestCase):
    def setUp(self):
        self.config = \
            {
                "sink": [
                    {
                        "name": "sink1",
                        "type": "EventHub",
                        "sasURL": "https://sbnamespace.servicebus.windows.net/raw?sr=https%3a%2f%2fsb"
                                  "namespace.servicebus.windows.net%2fraw%2f&sig=SIGNATURE%3d"
                                  "&se=1804371161&skn=writer"
                    },
                    {
                        "name": "sink2",
                        "type": "JsonBlob"
                    },
                    {
                        "name": "sink3",
                        "type": "EventHub",
                        "sasURL": "https://sbnamespace2.servicebus.windows.net/raw?sr=https%3a%2f%2fsb"
                                  "namespace.servicebus.windows.net%2fraw%2f&sig=SIGNATURE%3d"
                                  "&se=99999999999&skn=writer"
                    }
                ]
            }
        self.sink_config = LadUtil.SinkConfiguration()
        self.sink_config.insert_from_config(self.config)

    def test_insert_from_config(self):
        json_config = {}
        sinks = LadUtil.SinkConfiguration()
        msgs = sinks.insert_from_config(json_config)
        self.assertEqual(msgs, '')
        json_config = {'sink': [{'Name': 'bad case'}]}
        sinks = LadUtil.SinkConfiguration()
        msgs = sinks.insert_from_config(json_config)
        self.assertEqual(msgs, "Ignoring invalid sink definition {'Name': 'bad case'}")

    def test_get_all_sink_names(self):
        sinks = self.sink_config.get_all_sink_names()
        self.assertEqual(len(sinks), len(self.config["sink"]))
        self.assertIn("sink1", sinks)
        for sink in self.config["sink"]:
            self.assertIn(sink["name"], sinks)

    def helper_get_sink_by_name(self, name, type, sasURL=False):
        sink = self.sink_config.get_sink_by_name(name)
        self.assertIsNotNone(sink)
        self.assertEqual(sink['name'], name)
        self.assertEqual(sink['type'], type)
        if sasURL:
            self.assertIn('sasURL', sink)

    def test_get_sink_by_name(self):
        self.assertIsNone(self.sink_config.get_sink_by_name("BogusSink"))
        self.helper_get_sink_by_name('sink1', 'EventHub', True)
        self.helper_get_sink_by_name('sink2', 'JsonBlob')
        self.helper_get_sink_by_name('sink3', 'EventHub', True)

    def helper_get_sinks_by_type(self, type, names):
        sink_list = self.sink_config.get_sinks_by_type(type)
        self.assertEqual(len(sink_list), len(names))
        # Ugly nested loops... Please suggest any better Pythonic code
        names_from_sink_list = [sink['name'] for sink in sink_list]
        for name in names:
            self.assertIn(name, names_from_sink_list)

    def test_get_sinks_by_type(self):
        sink_list = self.sink_config.get_sinks_by_type("Bogus")
        self.assertEqual(len(sink_list), 0)
        self.helper_get_sinks_by_type('EventHub', ['sink1', 'sink3'])
        self.helper_get_sinks_by_type('JsonBlob', ['sink2'])

if __name__ == '__main__':
    unittest.main()
