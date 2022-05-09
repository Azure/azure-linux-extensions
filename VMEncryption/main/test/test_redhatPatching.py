import unittest
import os.path

from patch.redhatPatching import redhatPatching
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

class Test_redhatPatching(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()

    def test_online_enc_candidate_85(self):
        redhat_patching = redhatPatching(self.logger, ['redhat', '8.5'])
        self.assertTrue(redhat_patching.support_online_encryption)

    def test_online_enc_candidate_81(self):
        redhat_patching = redhatPatching(self.logger, ['redhat', '8.1'])
        self.assertTrue(redhat_patching.support_online_encryption)

    def test_online_enc_candidate_80(self):
        redhat_patching = redhatPatching(self.logger, ['redhat', '8.0'])
        self.assertFalse(redhat_patching.support_online_encryption)

    def test_online_enc_candidate_90(self):
        redhat_patching = redhatPatching(self.logger, ['redhat', '9.0'])
        self.assertTrue(redhat_patching.support_online_encryption)