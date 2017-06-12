# Make LadConfigAll class unittest-able here.
# To achieve that, the following were done:
# - Mock VM's cert/prv key files (w/ thumbprint) that's used for decrypting the extensions's protected settings
#   and for encrypting storage key/SAS token in mdsd XML file
# - Mock a complete LAD extension's handler setting (that includes protected settings and public settings).
# - Mock RunGetOutput for external command executions.
# - Mock any other things that are necessary!
# It'd be easiest to create a test VM w/ LAD enabled and copy out necessary files to here to be used for this test.
# The test VM was destroyed immediately. A test storage account was used and deleted immediately.
# TODO Try to generate priv key/cert/storage shared key dynamically here.

import binascii
import json
import os
import unittest
from xml.etree import ElementTree as ET
# This test suite uses xmlunittest package. Install it by running 'pip install xmlunittest'.
# Documentation at http://python-xmlunittest.readthedocs.io/en/latest/
from xmlunittest import XmlTestMixin

from Utils.lad_ext_settings import *
# The following line will work on an Azure Linux VM (where waagent is installed), but fail on a non-Azure Linux VM
# (because of no waagent). It's because lad_config_all.py will import misc_helpers.py, which will try to import
# waagent from WAAgentUtil.py.
# To work around this on a non-Azure Linux VM, define PYTHONPATH env var
# with "azure-linux-extensions/Common/WALinuxAgent-2.0.16" included in it.
# E.g., run 'export PYTHONPATH=<gitroot>/azure-linux-extensions/Common/WALinuxAgent-2.0.16' before running this test.
#
# Also, if you're trying to execute this test on a Windows system rather than under Linux, the waagent code relies on
# three Linux-only modules you'll need to mock out: crypt(crypt()), pwd(getpwnam()), and fcntl(ioctl()).
from lad_config_all import *

# Mocked waagent/LAD dir/files
test_waagent_dir = os.path.join(os.path.dirname(__file__), 'var_lib_waagent')
test_lad_dir = os.path.join(test_waagent_dir, 'lad_dir')
test_lad_settings_logging_json_file = os.path.join(test_lad_dir, 'config', 'lad_settings_logging.json')
test_lad_settings_metric_json_file = os.path.join(test_lad_dir, 'config', 'lad_settings_metric.json')


# Mocked functions

# We're not really interested in testing the ability to decrypt the private settings; that's tested elsewhere.
# Instead, we assume the test handlerSettings object contains the decrypted Private settings already, since we just
# need to test our ability to read and manipulate those settings.
def decrypt_protected_settings(handlerSettings):
    pass


def print_content_with_header(header_text, content):
    header = '>>>>> ' + header_text + ' >>>>>'
    print header
    print content
    print '<' * len(header)
    print


def mock_fetch_uuid():
    return "DEADBEEF-0000-1111-2222-77DEADBEEF77"


def mock_encrypt_secret(cert, secret):
    # Encode secret w/ binascii.hex() to avoid invalid chars in XML.
    # The actual/real return value of the non-mocked encrypt_secret() is in that form.
    # We still keep the "ENCRYPTED(...)" part here to show that clearly in our test outputs.
    secret = binascii.b2a_hex(secret).upper()
    return "ENCRYPTED({0},{1})".format(cert, secret)


def mock_log_info(msg):
    print 'LOG:', msg


def mock_log_error(msg):
    print 'ERROR:', msg


def load_test_config(filename):
    """
    Load a test configuration into a LadConfigAll object
    :param filename: Name of config file
    :rtype: LadConfigAll
    :return: Loaded configuration
    """
    with open(filename) as f:
        handler_settings = json.loads(f.read())['runtimeSettings'][0]['handlerSettings']
    decrypt_protected_settings(handler_settings)
    lad_settings = LadExtSettings(handler_settings)

    return LadConfigAll(lad_settings, test_lad_dir, '', 'test_lad_deployment_id', mock_fetch_uuid,
                        mock_encrypt_secret, mock_log_info, mock_log_error)


class LadConfigAllTest(unittest.TestCase, XmlTestMixin):
    def test_lad_config_all_logging_only(self):
        """
        Perform basic LadConfigAll object tests with logging-only configs,
        like generating various configs and validating them.
        """
        lad_cfg = load_test_config(test_lad_settings_logging_json_file)
        result, msg = lad_cfg.generate_all_configs()
        self.assertTrue(result, 'Config generation failed: ' + msg)

        with open(os.path.join(test_lad_dir, 'xmlCfg.xml')) as f:
            mdsd_xml_cfg = f.read()
        print_content_with_header('Generated mdsd XML cfg for logging-only LAD settings', mdsd_xml_cfg)
        self.assertTrue(mdsd_xml_cfg, 'Empty mdsd XML config is invalid!')

        rsyslog_cfg = lad_cfg.get_rsyslog_config()
        print_content_with_header('Generated rsyslog cfg', rsyslog_cfg)
        self.assertTrue(rsyslog_cfg, 'Empty rsyslog cfg is invalid')

        syslog_ng_cfg = lad_cfg.get_syslog_ng_config()
        print_content_with_header('Generated syslog-ng cfg', syslog_ng_cfg)
        self.assertTrue(syslog_ng_cfg, 'Empty syslog-ng cfg is invalid')

        fluentd_out_mdsd_cfg = lad_cfg.get_fluentd_out_mdsd_config()
        print_content_with_header('Generated fluentd out_mdsd cfg', fluentd_out_mdsd_cfg)
        self.assertTrue(fluentd_out_mdsd_cfg, 'Empty fluentd out_mdsd cfg is invalid')

        fluentd_syslog_src_cfg = lad_cfg.get_fluentd_syslog_src_config()
        print_content_with_header('Generated fluentd syslog src cfg', fluentd_syslog_src_cfg)
        self.assertTrue(fluentd_syslog_src_cfg, 'Empty fluentd syslog src cfg is invalid')

        fluentd_tail_src_cfg = lad_cfg.get_fluentd_tail_src_config()
        print_content_with_header('Generated fluentd tail src cfg', fluentd_tail_src_cfg)
        self.assertTrue(fluentd_tail_src_cfg, 'Empty fluentd tail src cfg is invalid')

    def test_lad_config_all_metric_only(self):
        """
        Perform basic LadConfigAll object tests with metric-only configs,
        like generating various configs and validating them.
        """
        lad_cfg = load_test_config(test_lad_settings_metric_json_file)
        result, msg = lad_cfg.generate_all_configs()
        self.assertTrue(result, 'Config generation failed: ' + msg)

        with open(os.path.join(test_lad_dir, 'xmlCfg.xml')) as f:
            mdsd_xml_cfg = f.read()
        print_content_with_header('Generated mdsd XML cfg for metric-only LAD settings', mdsd_xml_cfg)
        self.assertTrue(mdsd_xml_cfg, 'Empty mdsd XML config is invalid!')

        # Verify using xmlunittests
        root = self.assertXmlDocument(mdsd_xml_cfg)
        expected_xml_str = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2017-03-27T19:45:00.000" version="1.0">
  <Accounts>
    <SharedAccessSignature account="ladunittestfakeaccount" decryptKeyPath="B175B535DFE9F93659E5AFD893BF99BBF9DF28A5.prv" isDefault="true" key="ENCRYPTED(B175B535DFE9F93659E5AFD893BF99BBF9DF28A5.crt,4E4F545F415F5245414C5F544F4B454E)" moniker="moniker" tableEndpoint="https://ladunittestfakeaccount.table.core.windows.net/" />
  </Accounts>

  <Management defaultRetentionInDays="90" eventVolume="Large">
    <Identity>
      <IdentityComponent name="DeploymentId">test_lad_deployment_id</IdentityComponent>
      <IdentityComponent name="Host" useComputerName="true" />
    </Identity>
    <AgentResourceUsage diskQuotaInMB="50000" />
  <OboDirectPartitionField name="resourceId" value="ladtest_resource_id" />
  <OboDirectPartitionField name="agentIdentityHash" value="DEADBEEF-0000-1111-2222-77DEADBEEF77" />
  </Management>

  <Schemas>
  </Schemas>

  <Sources>
  </Sources>

  <Events>
    <MdsdEvents>
    </MdsdEvents>

    <OMI>
    <OMIQuery cqlQuery="SELECT FreeMegabytes FROM SCX_FileSystemStatisticalInformation WHERE Name='/'" eventName="builtin000003" omiNamespace="root/scx" sampleRateInSeconds="15" storeType="local">
  <Unpivot columnName="CounterName" columnValue="Value" columns="FreeMegabytes">
    <MapName name="FreeMegabytes" scaleUp="1048576">/builtin/filesystem/freespace(/mnt)</MapName>
  </Unpivot>
</OMIQuery><OMIQuery cqlQuery="SELECT UsedMegabytes FROM SCX_FileSystemStatisticalInformation WHERE Name=&quot;/&quot;" eventName="builtin000002" omiNamespace="root/scx" sampleRateInSeconds="15" storeType="local">
  <Unpivot columnName="CounterName" columnValue="Value" columns="UsedMegabytes">
    <MapName name="UsedMegabytes" scaleUp="1048576">/builtin/filesystem/usedspace</MapName>
  </Unpivot>
</OMIQuery><OMIQuery cqlQuery="SELECT PercentProcessorTime FROM SCX_ProcessorStatisticalInformation WHERE IsAggregate=TRUE" eventName="builtin000001" omiNamespace="root/scx" sampleRateInSeconds="15" storeType="local">
  <Unpivot columnName="CounterName" columnValue="Value" columns="PercentProcessorTime">
    <MapName name="PercentProcessorTime">/builtin/processor/PercentProcessorTime</MapName>
  </Unpivot>
</OMIQuery>
  <OMIQuery cqlQuery="SELECT PercentAvailableMemory, PercentUsedSwap FROM SCX_MemoryStatisticalInformation" dontUsePerNDayTable="true" eventName="LinuxMemory" omiNamespace="root/scx" priority="High" sampleRateInSeconds="300" />
  <OMIQuery cqlQuery="SELECT PercentAvailableMemory, PercentUsedSwap FROM SCX_MemoryStatisticalInformation" dontUsePerNDayTable="true" eventName="LinuxMemoryEventHub" omiNamespace="root/scx" priority="High" sampleRateInSeconds="300" storeType="local" />
  <OMIQuery cqlQuery="SELECT PercentProcessorTime FROM SCX_ProcessorStatisticalInformation" dontUsePerNDayTable="true" eventName="ProcessorInfoJsonBlob" omiNamespace="root/scx" priority="High" sampleRateInSeconds="60" storeType="JsonBlob" />
  <OMIQuery cqlQuery="SELECT PercentProcessorTime FROM SCX_ProcessorStatisticalInformation" dontUsePerNDayTable="true" eventName="ProcessorInfoEventHub" omiNamespace="root/scx" priority="High" sampleRateInSeconds="60" storeType="local" />
  <OMIQuery cqlQuery="SELECT FreeMegabytes FROM SCX_FileSystemStatisticalInformation" dontUsePerNDayTable="true" eventName="LinuxFileSystem" omiNamespace="root/scx" priority="High" sampleRateInSeconds="300" />
  <OMIQuery cqlQuery="SELECT FreeMegabytes FROM SCX_FileSystemStatisticalInformation" dontUsePerNDayTable="true" eventName="FileSystemJsonBlob" omiNamespace="root/scx" priority="High" sampleRateInSeconds="300" storeType="JsonBlob" />
  </OMI>

    <DerivedEvents>
    <DerivedEvent duration="PT1H" eventName="WADMetricsPT1HP10DV2S" isFullName="true" source="builtin000001" storeType="Central">
<LADQuery columnName="CounterName" columnValue="Value" instanceID="" partitionKey="ladtest:005Fresource:005Fid" />
</DerivedEvent><DerivedEvent duration="PT1M" eventName="WADMetricsPT1MP10DV2S" isFullName="true" source="builtin000001" storeType="Central">
<LADQuery columnName="CounterName" columnValue="Value" instanceID="" partitionKey="ladtest:005Fresource:005Fid" />
</DerivedEvent><DerivedEvent duration="PT1H" eventName="WADMetricsPT1HP10DV2S" isFullName="true" source="builtin000002" storeType="Central">
<LADQuery columnName="CounterName" columnValue="Value" instanceID="" partitionKey="ladtest:005Fresource:005Fid" />
</DerivedEvent><DerivedEvent duration="PT1M" eventName="WADMetricsPT1MP10DV2S" isFullName="true" source="builtin000002" storeType="Central">
<LADQuery columnName="CounterName" columnValue="Value" instanceID="" partitionKey="ladtest:005Fresource:005Fid" />
</DerivedEvent><DerivedEvent duration="PT1H" eventName="WADMetricsPT1HP10DV2S" isFullName="true" source="builtin000003" storeType="Central">
<LADQuery columnName="CounterName" columnValue="Value" instanceID="" partitionKey="ladtest:005Fresource:005Fid" />
</DerivedEvent><DerivedEvent duration="PT1M" eventName="WADMetricsPT1MP10DV2S" isFullName="true" source="builtin000003" storeType="Central">
<LADQuery columnName="CounterName" columnValue="Value" instanceID="" partitionKey="ladtest:005Fresource:005Fid" />
</DerivedEvent></DerivedEvents>
  </Events>

  <EventStreamingAnnotations>
  <EventStreamingAnnotation name="LinuxMemoryEventHub">
       <EventPublisher>
         <Key decryptKeyPath="B175B535DFE9F93659E5AFD893BF99BBF9DF28A5.prv">ENCRYPTED(B175B535DFE9F93659E5AFD893BF99BBF9DF28A5.crt,68747470733A2F2F66616B65267361732575726C3B31)</Key>
       </EventPublisher>
    </EventStreamingAnnotation><EventStreamingAnnotation name="ProcessorInfoEventHub">
       <EventPublisher>
         <Key decryptKeyPath="B175B535DFE9F93659E5AFD893BF99BBF9DF28A5.prv">ENCRYPTED(B175B535DFE9F93659E5AFD893BF99BBF9DF28A5.crt,68747470733A2F2F66616B65267361732575726C3B32)</Key>
       </EventPublisher>
    </EventStreamingAnnotation></EventStreamingAnnotations>

</MonitoringManagement>

"""
        # The following is at least insensitive to whitespaces... Also it's way more complicated
        # to create XPaths for this, so just use the following API.
        self.assertXmlEquivalentOutputs(mdsd_xml_cfg, expected_xml_str)

    def test_update_metric_collection_settings(self):
        test_config = \
            {
                "diagnosticMonitorConfiguration":
                    {
                        "foo": "bar",
                        "eventVolume": "Large",
                        "sinksConfig": {
                            "sink": [
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
                            "syslogEventConfiguration": {
                                "LOG_LOCAL1": "LOG_INFO",
                                "LOG_MAIL": "LOG_FATAL"
                            }
                        }
                    },
                "sampleRateInSeconds": 60
            }

        test_sinks_config = \
            {
                "sink": [
                    {
                        "name": "sink1",
                        "type": "EventHub",
                        "sasURL": "https://sbnamespace.servicebus.windows.net/raw?sr=https%3a%2f%2fsb"
                                  "namespace.servicebus.windows.net%2fraw%2f&sig=SIGNATURE%3d"
                                  "&se=1804371161&skn=writer"
                    }
                ]
            }

        configurator = load_test_config(test_lad_settings_logging_json_file)
        configurator._sink_configs.insert_from_config(test_sinks_config)
        configurator._update_metric_collection_settings(test_config)
        print ET.tostring(configurator._mdsd_config_xml_tree.getroot())

if __name__ == '__main__':
    unittest.main()
