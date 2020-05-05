#!/usr/bin/env python

import os
import pwd
import shutil
import tempfile
import unittest
import Utils.extensionutils as ext_utils
import Utils.logger


ext_utils.logger = Utils.logger.TestLogger()


class TestCodeInjection(unittest.TestCase):
    test_dir = "./test_output"

    def get_random_filename(self):
        return tempfile.mktemp(dir=TestCodeInjection.test_dir)

    def cleanup(self):
        shutil.rmtree(TestCodeInjection.test_dir)

    def setup(self):
        current_user = pwd.getpwuid(os.getuid())
        ext_utils.create_dir(TestCodeInjection.test_dir, current_user.pw_name, 0o700)

    def test_code_injection(self):
        # failure cases
        exit_code, string_output = ext_utils.run_command_get_output("echo hello; echo world")
        self.assertNotEqual(0, exit_code, "exit code != 0")
        exit_code, string_output = ext_utils.run_command_get_output(["echo hello; echo world"])
        self.assertNotEqual(0, exit_code, "exit code != 0")

        # success case
        exit_code, string_output = ext_utils.run_command_get_output(["echo", "hello", ";", "echo", "world"])
        self.assertEqual(0, exit_code, "exit code == 0")
        self.assertEqual("hello ; echo world\n", string_output, "unexpected output")
        exit_code, string_output = ext_utils.run_command_get_output(["echo", "hello", "world"])
        self.assertEqual(0, exit_code, "exit code == 0")

    def test_code_injection2(self):
        self.setup()
        self.addCleanup(self.cleanup)
        # failure cases
        out_file = self.get_random_filename()
        exit_code = ext_utils.run_command_and_write_stdout_to_file(
            "echo hello; echo world", out_file)
        self.assertNotEqual(0, exit_code, "exit code != 0")

        out_file = self.get_random_filename()
        exit_code = ext_utils.run_command_and_write_stdout_to_file(
            ["echo hello; echo world"], out_file)
        self.assertNotEqual(0, exit_code, "exit code != 0")

        # success case
        out_file = self.get_random_filename()
        exit_code = ext_utils.run_command_and_write_stdout_to_file(
            ["echo", "hello", ";", "echo", "world"], out_file)
        self.assertEqual(0, exit_code, "exit code == 0")
        file_contents = ext_utils.get_file_contents(out_file)
        self.assertEqual("hello ; echo world\n", file_contents, "unexpected output")

        out_file = self.get_random_filename()
        exit_code = ext_utils.run_command_and_write_stdout_to_file([
            "echo", "hello", "world"], out_file)
        self.assertEqual(0, exit_code, "exit code == 0")
        file_contents = ext_utils.get_file_contents(out_file)
        self.assertEqual("hello world\n", file_contents, "unexpected output")


if __name__ == '__main__':
    unittest.main()
