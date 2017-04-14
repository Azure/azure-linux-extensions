from unittest import TestCase
import Providers.Builtin as BProvider
import Utils.ProviderUtil as ProvUtil
import xml.etree.ElementTree as ET


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


class TestMakeXML(TestCase):
    def setUp(self):
        self.base_xml = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2017-03-27T19:45:00.000" version="1.0">
  <Accounts>
    <Account account="" isDefault="true" key="" moniker="moniker" tableEndpoint="" />
    <SharedAccessSignature account="" isDefault="true" key="" moniker="moniker" tableEndpoint="" />
  </Accounts>

  <Management defaultRetentionInDays="90" eventVolume="">
    <Identity>
      <IdentityComponent name="DeploymentId" />
      <IdentityComponent name="Host" useComputerName="true" />
    </Identity>
    <AgentResourceUsage diskQuotaInMB="50000" />
  </Management>

  <Schemas>
  </Schemas>

  <Sources>
  </Sources>

  <Events>
    <MdsdEvents>
    </MdsdEvents>

    <OMI>
    </OMI>

    <DerivedEvents>
    </DerivedEvents>
  </Events>

  <EventStreamingAnnotations>
  </EventStreamingAnnotations>

</MonitoringManagement>
"""

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
