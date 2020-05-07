#!/usr/bin/env python

import os.path as path
import unittest
import Utils.extensionutils as ext_utils
import Utils.ovfutils as ovf_utils
import Utils.logger as logger


Configuration = ext_utils.ConfigurationProvider(None)

logger.global_shared_context_logger = logger.TestLogger()


class TestTestOvfUtils(unittest.TestCase):
    def test_ovf_env_parse(self):
        current_dir = d = path.dirname(path.abspath(__file__))
        ovf_xml = ext_utils.get_file_contents(path.join(current_dir, 'ovf-env.xml'))
        ovf_env = ovf_utils.OvfEnv.parse(ovf_xml, Configuration)
        self.assertIsNotNone(ovf_env, "ovf_env should not be null")


if __name__ == '__main__':
    unittest.main()
