import sys
sys.path.insert(1, './../')
import json 
import Utils.telegraf_config_parser as telparser
import os
import unittest


sample_lad_config_input = [{'interval': u'15s', 'displayName': u'filesystem->Filesystem % used space'}, {'interval': u'15s', 'displayName': u'filesystem->Filesystem used space'}, {'interval': u'15s', 'displayName': u'filesystem->Filesystem read bytes/sec'}, {'interval': u'15s', 'displayName': u'filesystem->Filesystem free space'}]
sample_missspelled_lad_config_input = [{'interval': u'15s', 'displayName': u'filesystem->Filesystem sed space'},{'interval': u'15s', 'displayName': u'filesystem-Filesystem free space'}]


sample_agent_conf = """[agent]\n  interval = "10s"\n  round_interval = true  metric_batch_size = 1000\n  metric_buffer_limit = 10000\n  collection_jitter = "0s"\n  flush_interval = "10s"\n  flush_jitter = "0s"\n  logtarget = "file"\n  logfile = "/var/log/azure/Microsoft.Azure.Diagnostics.LinuxDiagnostic/telegraf.log"\n  logfile_rotation_max_size = "100MB"\n  logfile_rotation_max_archives = 5\n\n# Configuration for sending metrics to InfluxD\n[[outputs.influxdb]]\n"""
sample_filesystem_conf = """[[inputs.disk]]\n  fieldpass = ["used_percent", "used", "free"]\n  interval = "15s"\n\n[[inputs.diskio]]\n  fieldpass = ["read_bytes"]\n  interval = "15s"\n\n\n\n[[processors.rename]]\n  namepass = ["disk"]\n\n  [[processors.rename.replace]]\n    field = "used_percent"\n    dest = "Filesystem % used space"\n\n  [[processors.rename.replace]]\n    field = "used"\n    dest = "Filesystem used space"\n\n  [[processors.rename.replace]]\n    field = "free"\n    dest = "Filesystem free space"\n\n\n[[processors.rename]]\n  namepass = ["diskio"]\n\n  [[processors.rename.replace]]\n    field = "read_bytes_rate"\n    dest = "Filesystem read bytes/sec"\n\n\n[[aggregators.basicstats]]\n  period = "30s"\n  drop_original = false\n  fieldpass = ["read_bytes"]\n  stats = ["rate"]\n  rate_period = "30s"\n\n"""
sample_int_json = """{"filesystem": {"disk": {"used_percent": {"interval": "15s", "displayName": "Filesystem % used space"}, "used": {"interval": "15s", "displayName": "Filesystem used space"}, "free": {"interval": "15s", "displayName": "Filesystem free space"}}, "diskio": {"read_bytes": {"interval": "15s", "displayName": "Filesystem read bytes/sec", "op": "rate"}}}}"""

class TelegrafConfigParserTest(unittest.TestCase):
    def test_telegraf_agent_config(self):
        output = telparser.parse_config(sample_lad_config_input)
        agentconf = None
        for k in output:
            if k["filename"] == "telegraf.conf":
                agentconf = k["data"]
        self.assertIsNotNone(agentconf)
        self.assertEqual(sample_agent_conf, agentconf)


    def test_telegraf_module_config(self):
        output = telparser.parse_config(sample_lad_config_input)
        moduleconf = None
        for k in output:
            if k["filename"] == "filesystem.conf":
                moduleconf = k["data"]
        self.assertIsNotNone(moduleconf)
        self.assertEqual(sample_filesystem_conf, moduleconf)


    def test_telegraf_intermediate_json(self):
        output = telparser.parse_config(sample_lad_config_input)
        intjson = None
        for k in output:
            if k["filename"] == "intermediate.json":
                intjson = k["data"]
        self.assertIsNotNone(intjson)
        self.assertEqual(sample_int_json, intjson)

    
    def test_telegraf_empty_agent_config(self):
        output = telparser.parse_config([])
        agentconf = None
        self.assertIsNone(agentconf)
        self.assertEqual([], output)


    def test_telegraf_miss_spelled_config_agent_config(self):
        output = None
        with self.assertRaises(Exception) as eobj:
            output = telparser.parse_config(sample_missspelled_lad_config_input)

        self.assertEqual("Unable to parse telegraf config into intermediate dictionary.", eobj.exception.message)
        self.assertIsNone(output)

if __name__ == "__main__":
    unittest.main()