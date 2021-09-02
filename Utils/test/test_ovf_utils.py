#!/usr/bin/env python

import os.path as path
import unittest
import Utils.extensionutils as ext_utils
import Utils.ovfutils as ovf_utils
import Utils.logger as logger


# dummy configuration class based on vmaccess.Configuration
class Configuration:
    def __init__(self):
        self.dictionary = {
            "Provisioning.DecodeCustomData": "n"
        }

    def get(self, key):
        return self.dictionary.get(key)


config = Configuration()

logger.global_shared_context_logger = logger.TestLogger()


class TestTestOvfUtils(unittest.TestCase):
    def test_ovf_env_parse(self):
        current_dir = path.dirname(path.abspath(__file__))
        ovf_xml = ext_utils.get_file_contents(path.join(current_dir, 'ovf-env.xml'))
        ovf_env = ovf_utils.OvfEnv.parse(ovf_xml, config)
        self.assertIsNotNone(ovf_env, "ovf_env should not be null")

    def test_ovf_env_parse_minimalxml(self):
        current_dir = path.dirname(path.abspath(__file__))
        ovf_xml = ext_utils.get_file_contents(path.join(current_dir, 'ovf-env-empty.xml'))
        ovf_env = ovf_utils.OvfEnv.parse(ovf_xml, config)
        self.assertIsNone(ovf_env, "ovf_env should be null")

    def test_ovf_env_parse_none_string(self):
        ovf_env = ovf_utils.OvfEnv.parse(None, config)
        self.assertIsNone(ovf_env, "ovf_env should be null")

    def test_ovf_env_parse_empty_string(self):
        ovf_env = ovf_utils.OvfEnv.parse("", config)
        self.assertIsNone(ovf_env, "ovf_env should be null")


if __name__ == '__main__':
    unittest.main()
