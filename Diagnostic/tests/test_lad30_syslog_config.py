import unittest

from Utils.lad30_syslog_config import RsyslogConfig

omazuremds_basic_json_ext_settings = """
"syslogEventConfiguration": {
    "LOG_USER": "LOG_ERR",
    "LOG_LOCAL0": "LOG_CRIT"
}
"""

omazuremds_basic_expected_output_legacy = """
# Expected omazuremds rsyslog output module config string corresponding to omazuremds_basic_json_ext_settings
# for rsyslog legacy versions (5/7)
"""

omazuremds_basic_expected_output = """
# Expected omazuremds rsyslog output module config string corresponding to omazuremds_basic_json_ext_settings
# for rsyslog non-legacy version (8)
"""

omazuremds_extended_json_ext_settings = """
[
    {
        "facility": "LOG_USER",
        "minSeverity": "LOG_ERR",
        "table": "SyslogUserErrorEvents"
    },
    {
        "facility": "LOG_LOCAL0",
        "minSeverity": "LOG_CRIT",
        "table": "SyslogLocal0CritEvents"
    }
]
"""

omazuremds_extended_expected_output_legacy = """
# Expected omazuremds rsyslog output module config string corresponding to omazuremds_extended_json_ext_settings
# for rsyslog legacy versions (5/7)
"""

omazuremds_extended_expected_output = """
# Expected omazuremds rsyslog output module config string corresponding to omazuremds_extended_json_ext_settings
# for rsyslog non-legacy version (8)
"""

imfile_basic_json_ext_settings = """
[
    {
        "file": "/var/log/mydaemonlog",
        "table": "MyDaemonEvents"
    },
    {
        "file": "/var/log/myotherdaemonelog",
        "table": "MyOtherDaemonEvents"
    }
]
"""

imfile_basic_expected_output = """
# Expected imfile rsyslog input module config string corresponding to imfile_basic_json_ext_settings
"""

class Lad30RsyslogConfigTest(unittest.TestCase):

    def test_omazuremds_basic(self):
        pass

    def test_omazuremds_extended(self):
        pass

    def test_imfile_basic(self):
        pass


if __name__ == '__main__':
    unittest.main()
