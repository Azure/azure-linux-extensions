import unittest
from CommandExecutor import CommandExecutor
from .console_logger import ConsoleLogger

class TestCommandExecutor(unittest.TestCase):
    """ unit tests for functions in the CommandExecutor module """
    def setUp(self):
        self.logger = ConsoleLogger()
        self.cmd_executor = CommandExecutor(self.logger)

    def test_command_timeout(self):
        return_code = self.cmd_executor.Execute('sleep 15', timeout=10)
        self.assertEqual(return_code, -9, msg="The command didn't timeout as expected")

    def test_command_no_timeout(self):
        return_code = self.cmd_executor.Execute('sleep 5', timeout=10)
        self.assertEqual(return_code, 0, msg="The command should have completed successfully")