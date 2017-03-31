from unittest import TestCase
import LadDiagnosticUtil as LadUtil


class TestGetDiagnosticsMonitorConfigurationElement(TestCase):
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
                            "LOG_LOCAL1": "LOG_INFO",
                            "LOG_MAIL": "LOG_FATAL"
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

    def test_getAllDefinedSinksFromLadCfg(self):
        sinks = LadUtil.getAllDefinedSinksFromLadCfg(self.valid_config)
        self.assertEqual(len(sinks), 1)
        self.assertIn("sink1", sinks)

    def test_getSinkDefinitionFromLadCfg(self):
        self.assertIsNone(LadUtil.getSinkDefinitionFromLadCfg(self.valid_config, "BogusSink"))
        sink = LadUtil.getSinkDefinitionFromLadCfg(self.valid_config, "sink1")
        self.assertIsNotNone(sink)
        self.assertEqual(sink['name'], 'sink1')
        self.assertEqual(sink['type'], 'EventHub')
        self.assertIn('sasURL', sink)

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
