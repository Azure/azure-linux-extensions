#!/usr/bin/env python

import unittest
import Utils.extensionutils as ext_utils
import Utils.logger

ext_utils.logger = Utils.logger.TestLogger()


class TestCodeInjection(unittest.TestCase):
    def test_code_injection(self):
        # failure cases
        exit_code, string_output = ext_utils.run_command_get_output("echo hello; echo world")
        self.assertNotEquals(0, exit_code, "exit code != 0")
        exit_code, string_output = ext_utils.run_command_get_output(["echo hello; echo world"])
        self.assertNotEquals(0, exit_code, "exit code != 0")

        # success case
        exit_code, string_output = ext_utils.run_command_get_output(["echo", "hello", ";", "echo", "world"])
        self.assertEquals(0, exit_code, "exit code == 0")
        self.assertEquals("hello ; echo world\n", string_output, "unexpected output")
        exit_code, string_output = ext_utils.run_command_get_output(["echo", "hello", "world"])
        self.assertEquals(0, exit_code, "exit code == 0")


if __name__ == '__main__':
    unittest.main()
