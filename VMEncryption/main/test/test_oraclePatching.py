import unittest
import os.path

from patch.oraclePatching import oraclePatching
from DiskUtil import DiskUtil
from Common import CommonVariables
from CommandExecutor import CommandExecutor
from .console_logger import ConsoleLogger
try:
    builtins_open = "builtins.open"
    import unittest.mock as mock # python3+
except ImportError:
    builtins_open = "__builtin__.open"
    import mock # python2

class Test_oraclePatching(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()

    def test_online_enc_candidate_85(self):
        oracle_patching = oraclePatching(self.logger, ['oracle', '8.5'])
        self.assertTrue(oracle_patching.support_online_encryption)

    def test_online_enc_candidate_84(self):
        oracle_patching = oraclePatching(self.logger, ['oracle', '8.4'])
        self.assertFalse(oracle_patching.support_online_encryption)

    def test_online_enc_candidate_90(self):
        oracle_patching = oraclePatching(self.logger, ['oracle', '9.0'])
        self.assertTrue(oracle_patching.support_online_encryption)