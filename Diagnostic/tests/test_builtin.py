import unittest
import Providers.Builtin as BProvider
import Utils.ProviderUtil as ProvUtil
from Utils.mdsd_xml_templates import entire_xml_cfg_tmpl
import xml.etree.ElementTree as ET
import json
import re


class TestBuiltinMetric(unittest.TestCase):
    def setUp(self):
        self.basic_valid = {
            "type": "builtin",
            "class": "Processor",
            "counter": "PercentIdleTime",
            "counterSpecifier": "/builtin/Processor/PercentIdleTime",
            "condition": 'IsAggregate=TRUE',
            "sampleRate": "PT30S",
            "unit": "Percent",
            "annotation": [
                {
                    "displayName": "Aggregate CPU %idle time",
                    "locale": "en-us"
                }
            ]
        }
        self.mapped = {
            "type": "builtin",
            "class": "filesystem",
            "counter": "Freespace",
            "counterSpecifier": "/builtin/Filesystem/Freespace(/)",
            "condition": 'Name="/"',
            "unit": "Bytes",
            "annotation": [
                {
                    "displayName": "Free space on /",
                    "locale": "en-us"
                }
            ]
        }

    def test_IsType(self):
        try:
            item = BProvider.BuiltinMetric(self.basic_valid)
            self.assertTrue(item.is_type('builtin'))
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_Class(self):
        dupe = self.basic_valid.copy()
        del dupe['class']
        self.assertRaises(ProvUtil.InvalidCounterSpecification, BProvider.BuiltinMetric, dupe)
        try:
            metric = BProvider.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.class_name(), 'processor')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_Counter(self):
        dupe = self.basic_valid.copy()
        del dupe['counter']
        self.assertRaises(ProvUtil.InvalidCounterSpecification, BProvider.BuiltinMetric, dupe)
        try:
            metric = BProvider.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.counter_name(), 'PercentIdleTime')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))
        try:
            metric = BProvider.BuiltinMetric(self.mapped)
            self.assertEqual(metric.counter_name(), 'FreeMegabytes')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_condition(self):
        dupe = self.basic_valid.copy()
        del dupe['condition']
        try:
            metric = BProvider.BuiltinMetric(dupe)
            self.assertIsNone(metric.condition())
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (dupe) raised exception: {0}".format(ex))
        try:
            metric = BProvider.BuiltinMetric(self.mapped)
            self.assertEqual(metric.condition(), 'Name="/"')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (self.mapped) raised exception: {0}".format(ex))
        try:
            metric = BProvider.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.condition(), 'IsAggregate=TRUE')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (self.basic_valid) raised exception: {0}".format(ex))

    def test_label(self):
        dupe = self.basic_valid.copy()
        del dupe['counterSpecifier']
        self.assertRaises(ProvUtil.InvalidCounterSpecification, BProvider.BuiltinMetric, dupe)
        try:
            metric = BProvider.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.label(), '/builtin/Processor/PercentIdleTime')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_sample_rate(self):
        try:
            metric = BProvider.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.sample_rate(), 30)
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))
        dupe = self.basic_valid.copy()
        del dupe['sampleRate']
        try:
            metric = BProvider.BuiltinMetric(dupe)
            self.assertEqual(metric.sample_rate(), 15)
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))


class TestMakeXML(unittest.TestCase):
    def setUp(self):
        self.base_xml = entire_xml_cfg_tmpl
    def test_two_and_two(self):
        specs = [
            {
                "type": "builtin",
                "class": "Processor",
                "counter": "PercentIdleTime",
                "counterSpecifier": "/builtin/Processor/PercentIdleTime",
                "condition": "IsAggregate=TRUE",
                "sampleRate": "PT30S",
            },
            {
                "type": "builtin",
                "class": "filesystem",
                "counter": "Freespace",
                "counterSpecifier": "/builtin/Filesystem/Freespace(/)",
                "condition": "Name='/'",
            },
            {
                "type": "builtin",
                "class": "Processor",
                "counter": "PercentProcessorTime",
                "counterSpecifier": "/builtin/Processor/PercentProcessorTime",
                "condition": "IsAggregate=TRUE",
                "sampleRate": "PT30S",
            },
            {
                "type": "builtin",
                "class": "filesystem",
                "counter": "Freespace",
                "counterSpecifier": "/builtin/Filesystem/Freespace(/mnt)",
                "condition": "Name=\"/mnt\"",
            },
        ]

        sink_names = set()
        for spec in specs:
            try:
                sink = BProvider.AddMetric(spec)
                self.assertIsNotNone(sink)
                sink_names.add(sink)
            except Exception as ex:
                self.fail("AddMetric({0}) raised exception: {1}".format(spec, ex))
        self.assertEqual(len(sink_names), 3)

        doc = ET.ElementTree(ET.fromstring(self.base_xml))
        BProvider.UpdateXML(doc)
        # xml_string = ET.tostring(doc.getroot())
        # print xml_string


class Lad2_3CompatiblePortalPublicSettingsGenerator(unittest.TestCase):

    @unittest.skip("Lad2_3Compat test needs redesign to be useful outside of internal development environment")
    def test_lad_2_3_compatible_portal_public_settings(self):
        """
        This is rather a utility function that attempts to generate a standard LAD 3.0 protected settings JSON string
        for the Azure Portal charts experience. Unit, displayName, and condition are inferred/auto-filled from
        a sample Azure Insights metric definitions JSON pulled from ACIS.
        """
        pub_settings = {
            "StorageAccount": "__DIAGNOSTIC_STORAGE_ACCOUNT__",
            "ladCfg": {
                "sampleRateInSeconds": 15,
                "diagnosticMonitorConfiguration": {
                    "eventVolume": "Medium",
                    "metrics": {
                        "metricAggregation": [
                            {
                                "scheduledTransferPeriod": "PT1H"
                            },
                            {
                                "scheduledTransferPeriod": "PT1M"
                            }
                        ],
                        "resourceId": "__VM_RESOURCE_ID__"
                    },
                    "performanceCounters": {
                        "performanceCounterConfiguration": []
                    },
                    "syslogEvents": {
                        "syslogEventConfiguration": {
                            'LOG_AUTH': 'LOG_DEBUG',
                            'LOG_AUTHPRIV': 'LOG_DEBUG',
                            'LOG_CRON': 'LOG_DEBUG',
                            'LOG_DAEMON': 'LOG_DEBUG',
                            'LOG_FTP': 'LOG_DEBUG',
                            'LOG_KERN': 'LOG_DEBUG',
                            'LOG_LOCAL0': 'LOG_DEBUG',
                            'LOG_LOCAL1': 'LOG_DEBUG',
                            'LOG_LOCAL2': 'LOG_DEBUG',
                            'LOG_LOCAL3': 'LOG_DEBUG',
                            'LOG_LOCAL4': 'LOG_DEBUG',
                            'LOG_LOCAL5': 'LOG_DEBUG',
                            'LOG_LOCAL6': 'LOG_DEBUG',
                            'LOG_LOCAL7': 'LOG_DEBUG',
                            'LOG_LPR': 'LOG_DEBUG',
                            'LOG_MAIL': 'LOG_DEBUG',
                            'LOG_NEWS': 'LOG_DEBUG',
                            'LOG_SYSLOG': 'LOG_DEBUG',
                            'LOG_USER': 'LOG_DEBUG',
                            'LOG_UUCP': 'LOG_DEBUG'
                        }
                    }
                }
            }
        }
        each_perf_counter_cfg_template = {
            "unit": "__TO_BE_FILLED__",
            "type": "builtin",
            "class": "__TO_BE_REPLACED_BY_CODE",
            "counter": "__TO_BE_REPLACED_BY_CODE__",
            "counterSpecifier": "__TO_BE_REPLACED_BY_CODE__",
            "annotation": "__TO_BE_FILLED__",  # Needs to be assigned a new instance to avoid shallow copy
            # [
            #     {
            #         "locale": "en-us",
            #         "displayName": "__TO_BE_FILLED__"
            #     }
            # ],
            "condition": "__TO_BE_FILLED__"
        }

        perf_counter_cfg_list = pub_settings['ladCfg']['diagnosticMonitorConfiguration']['performanceCounters']['performanceCounterConfiguration']
        units_and_names = self.extract_perf_counter_units_and_names_from_metrics_def_sample()

        for class_name in BProvider._builtIns:
            for lad_counter_name, scx_counter_name in BProvider._builtIns[class_name].iteritems():
                perf_counter_cfg = dict(each_perf_counter_cfg_template)
                perf_counter_cfg['class'] = class_name
                perf_counter_cfg['counter'] = lad_counter_name
                counter_specifier = '/builtin/{0}/{1}'.format(class_name, lad_counter_name)
                perf_counter_cfg['counterSpecifier'] = counter_specifier
                perf_counter_cfg['condition'] = BProvider.default_condition(class_name)
                if not perf_counter_cfg['condition']:
                    del perf_counter_cfg['condition']
                counter_specifier_with_scx_name = '/builtin/{0}/{1}'.format(class_name.title(), scx_counter_name)
                if counter_specifier_with_scx_name in units_and_names:
                    perf_counter_cfg['unit'] = units_and_names[counter_specifier_with_scx_name]['unit']
                    perf_counter_cfg['annotation'] = [{
                        'displayName': units_and_names[counter_specifier_with_scx_name]['displayName'],
                        'locale': 'en-us'
                    }]
                else:
                    # Use some ad hoc logic to auto-fill missing values (all from FileSystem class)
                    perf_counter_cfg['unit'] = self.inferred_unit_name_from_counter_name(scx_counter_name)
                    perf_counter_cfg['annotation'] = [{
                        'displayName': self.inferred_display_name_from_class_counter_names(class_name, scx_counter_name),
                        'locale': 'en-us'
                    }]
                perf_counter_cfg_list.append(perf_counter_cfg)

        actual = json.dumps(pub_settings, sort_keys=True, indent=2)
        print actual
        # Uncomment the following 2 lines when generating expected JSON file (of course after validating the actual)
        #with open('lad_2_3_compatible_portal_pub_settings.json', 'w') as f:
        #    f.write(actual)
        with open('lad_2_3_compatible_portal_pub_settings.json') as f:
            expected = f.read()
        self.assertEqual(json.dumps(json.loads(expected), sort_keys=True),
                         json.dumps(json.loads(actual), sort_keys=True))
        to_be_filled = re.findall(r'"__.*?__"', actual)
        self.assertEqual(2, len(to_be_filled))
        self.assertIn('"__DIAGNOSTIC_STORAGE_ACCOUNT__"', to_be_filled)
        self.assertIn('"__VM_RESOURCE_ID__"', to_be_filled)

    def inferred_unit_name_from_counter_name(self, scx_counter_name):
        if 'Percent' in scx_counter_name:
            return 'Percent'
        if re.match(r'Bytes.*PerSecond', scx_counter_name):
            return 'BytesPerSecond'  # According to the ACIS-pulled metric definitions sample...
        if 'PerSecond' in scx_counter_name:
            return 'CountPerSecond'  # Again according to the ACIS-pulled metric defs sample...
        if scx_counter_name in BProvider._scaling['memory'] or scx_counter_name in BProvider._scaling['filesystem']:
            return 'Bytes'  # Scaled MiB to Bytes counters, so use Bytes as unit
        raise Exception("Can't infer unit name from scx counter name ({0})".format(scx_counter_name))

    def inferred_display_name_from_class_counter_names(self, class_name, scx_counter_name):
        desc = scx_counter_name
        desc = desc.replace('PerSecond', '/sec')
        desc = ' '.join([word.lower() for word in re.findall('[A-Z]+[^A-Z]*', desc)])
        desc = desc.replace('percent', '%').replace('megabytes', 'space')
        return '{0} {1}'.format(class_name.title(), desc)

    def extract_perf_counter_units_and_names_from_metrics_def_sample(self):
        """
        Another utility function that extracts perf counter units and display names from an Azure metrics
        definition sample file (not included in the repo). Again this is to be used only manually under
        the desired environment when needed.
        :return: Dictionary of counter specifier to unit/displayName map.
        """
        results = {}
        metric_definitions = {}
        with open('lad_2_3_metric_definitions_sample.json') as f:
            metric_definitions = json.load(f)
        for dict_item in metric_definitions['value']:  # This is a list of dictionaries for all metrics
            # E.g., '\\Memory\\AvailableMemory' to '/builtin/Memory/AvailableMemory'
            # Also, Azure Insights uses 'PhysicalDisk' and 'NetworkInterface' instead of 'Disk' and 'Network',
            # so replace them as well.
            counter_specifier = '/builtin{0}'.format(dict_item['name']['value'].replace('\\', '/')
                                                     .replace('PhysicalDisk', 'Disk')
                                                     .replace('NetworkInterface', 'Network'))
            display_name = dict_item['name']['localizedValue']  # E.g., 'Memory available'
            unit = dict_item['unit']  # E.g., 'Bytes'
            results[counter_specifier] = { 'unit': unit, 'displayName': display_name }
        return results

if __name__ == '__main__':
    unittest.main()
