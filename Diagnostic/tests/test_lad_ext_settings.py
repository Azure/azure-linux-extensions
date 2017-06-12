import json
import unittest

from Utils.lad_ext_settings import *

class LadExtSettingsTest(unittest.TestCase):

    def setUp(self):
        handler_settings_sample_in_str = """
{
  "protectedSettings": {
    "storageAccountName": "mystgacct",
    "storageAccountSasToken": "SECRET",
    "sinksConfig": {
      "sink": [
        {
          "type": "JsonBlob",
          "name": "JsonBlobSink1"
        },
        {
          "type": "JsonBlob",
          "name": "JsonBlobSink2"
        },
        {
          "type": "EventHub",
          "name": "EventHubSink1",
          "sasURL": "SECRET"
        },
        {
          "type": "EventHub",
          "name": "EventHubSink2",
          "sasURL": "SECRET"
        }
      ]
    }
  },
  "publicSettings": {
    "StorageAccount": "mystgacct",
    "sampleRateInSeconds": 15,
    "fileLogs": [
      {
        "sinks": "EventHubSink1",
        "file": "/var/log/myladtestlog"
      }
    ]
  }
}
"""
        self._lad_settings = LadExtSettings(json.loads(handler_settings_sample_in_str))

    def test_redacted_handler_settings(self):
        expected = """
{
  "protectedSettings": {
    "sinksConfig": {
      "sink": [
        {
          "name": "JsonBlobSink1",
          "type": "JsonBlob"
        },
        {
          "name": "JsonBlobSink2",
          "type": "JsonBlob"
        },
        {
          "name": "EventHubSink1",
          "sasURL": "REDACTED_SECRET",
          "type": "EventHub"
        },
        {
          "name": "EventHubSink2",
          "sasURL": "REDACTED_SECRET",
          "type": "EventHub"
        }
      ]
    },
    "storageAccountName": "mystgacct",
    "storageAccountSasToken": "REDACTED_SECRET"
  },
  "publicSettings": {
    "StorageAccount": "mystgacct",
    "fileLogs": [
      {
        "file": "/var/log/myladtestlog",
        "sinks": "EventHubSink1"
      }
    ],
    "sampleRateInSeconds": 15
  }
}
"""
        actual_json = json.loads(self._lad_settings.redacted_handler_settings())
        print json.dumps(actual_json, sort_keys=True, indent=2)
        self.assertEqual(json.dumps(json.loads(expected), sort_keys=True),
                         json.dumps(actual_json, sort_keys=True))
        # Validate that the original wasn't modified (that is, redaction should be on a deep copy)
        print "===== Original handler setting (shouldn't be redacted, must be different from the deep copy) ====="
        print json.dumps(self._lad_settings.get_handler_settings(), sort_keys=True, indent=2)
        self.assertNotEqual(json.dumps(self._lad_settings.get_handler_settings(), sort_keys=True),
                            json.dumps(actual_json, sort_keys=True))

if __name__ == '__main__':
    unittest.main()
