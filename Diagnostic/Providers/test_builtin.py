from unittest import TestCase
import Providers.Builtin as builtin
import Utils.ProviderUtil as ProvUtil


class TestBuiltinMetric(TestCase):
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
                    "local": "en-us"
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
                    "local": "en-us"
                }
            ]
        }

    def test_IsType(self):
        try:
            item = builtin.BuiltinMetric(self.basic_valid)
            self.assertTrue(item.is_type('builtin'))
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_Class(self):
        dupe = self.basic_valid.copy()
        del dupe['class']
        self.assertRaises(ProvUtil.InvalidCounterSpecification, builtin.BuiltinMetric, dupe)
        try:
            metric = builtin.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.class_name(), 'processor')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))


    def test_Counter(self):
        dupe = self.basic_valid.copy()
        del dupe['counter']
        self.assertRaises(ProvUtil.InvalidCounterSpecification, builtin.BuiltinMetric, dupe)
        try:
            metric = builtin.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.counter_name(), 'percentidletime')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_omi_counter(self):
        try:
            metric = builtin.BuiltinMetric(self.mapped)
            self.assertEqual(metric.omi_counter(), 'freemegabytes')
            self.assertEqual(metric.counter_name(), 'freespace')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (self.mapped) raised exception: {0}".format(ex))
        try:
            metric = builtin.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.omi_counter(), 'percentidletime')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (self.basic_valid) raised exception: {0}".format(ex))

    def test_condition(self):
        dupe = self.basic_valid.copy()
        del dupe['condition']
        try:
            metric = builtin.BuiltinMetric(dupe)
            self.assertIsNone(metric.condition())
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (dupe) raised exception: {0}".format(ex))
        try:
            metric = builtin.BuiltinMetric(self.mapped)
            self.assertEqual(metric.condition(), 'Name="/"')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (self.mapped) raised exception: {0}".format(ex))
        try:
            metric = builtin.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.condition(), 'IsAggregate=TRUE')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor (self.basic_valid) raised exception: {0}".format(ex))

    def test_label(self):
        dupe = self.basic_valid.copy()
        del dupe['counterSpecifier']
        self.assertRaises(ProvUtil.InvalidCounterSpecification, builtin.BuiltinMetric, dupe)
        try:
            metric = builtin.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.label(), '/builtin/Processor/PercentIdleTime')
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))

    def test_sample_rate(self):
        try:
            metric = builtin.BuiltinMetric(self.basic_valid)
            self.assertEqual(metric.sample_rate(), 30)
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))
        dupe = self.basic_valid.copy()
        del dupe['sampleRate']
        try:
            metric = builtin.BuiltinMetric(dupe)
            self.assertEqual(metric.sample_rate(), 15)
        except Exception as ex:
            self.fail("BuiltinMetric Constructor raised exception: {0}".format(ex))
