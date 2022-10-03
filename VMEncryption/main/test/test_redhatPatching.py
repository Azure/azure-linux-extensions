import unittest
import os.path

from patch.redhatPatching import redhatPatching
from DiskUtil import DiskUtil
from Common import CommonVariables
from CommandExecutor import CommandExecutor
from .console_logger import ConsoleLogger
from CommandExecutor import ProcessCommunicator
try:
    builtins_open = "builtins.open"
    import unittest.mock as mock # python3+
except ImportError:
    builtins_open = "__builtin__.open"
    import mock # python2

class Test_redhatPatching(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.rh_patching = redhatPatching(self.logger, ['redhat', '8.5'])

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

    @mock.patch('os.path.exists')
    @mock.patch('CommandExecutor.CommandExecutor.ExecuteInBash')
    @mock.patch('filecmp.cmp')
    @mock.patch('CommandExecutor.ProcessCommunicator')
    @mock.patch('shutil.copyfile')
    def test_update_crypt_file(self, scf_mock, pcs_mock, fcmp_mock, ce_mock, exists_mock):
        dup_default_grub_content = "GRUB_TIMEOUT=10\n"\
        "GRUB_CMDLINE_LINUX=\"loglevel=3 crashkernel=auto console=tty1 console=ttyS0 earlyprintk=ttyS0 rootdelay=300 rd.luks.ade.partuuid=0f096480-83b8-4b90-ab0c-459c7a76f2fa rd.luks.ade.bootuuid=08797355-7e02-41e1-803a-0aed82b111bd rd.debug\""\
        "GRUB_TERMINAL=\"serial console\""\
        "GRUB_CMDLINE_LINUX+=\" rd.luks.ade.partuuid=0f096480-83b8-4b90-ab0c-459c7a76f2fa rd.luks.ade.bootuuid=08797355-7e02-41e1-803a-0aed82b111bd rd.debug \""

        correct_default_grub_content = "GRUB_TIMEOUT=10\n"\
        "GRUB_CMDLINE_LINUX=\"loglevel=3 crashkernel=auto console=tty1 console=ttyS0 earlyprintk=ttyS0 rootdelay=300\""\
        "GRUB_TERMINAL=\"serial console\""\
        "GRUB_CMDLINE_LINUX+=\" rd.luks.ade.partuuid=0f096480-83b8-4b90-ab0c-459c7a76f2fa rd.luks.ade.bootuuid=08797355-7e02-41e1-803a-0aed82b111bd rd.debug \""

        old_crypt_file_content = "PARTUUID=$(getargs rd.luks.ade.partuuid -d rd_LUKS_PARTUUID)\n"\
        "PARTUUID=$(getargs rd.luks.ade.partuuid -d rd_LUKS_PARTUUID)"

        new_crypt_file_content = "PARTUUID=$(getarg rd.luks.ade.partuuid -d rd_LUKS_PARTUUID)\n"\
        "PARTUUID=$(getarg rd.luks.ade.partuuid -d rd_LUKS_PARTUUID)"

        #Test 1: ADE dracut module not present
        exists_mock.return_value = False
        self.rh_patching.update_crypt_parse_file()
        self.assertEqual(exists_mock.call_count, 1)
        self.assertEqual(fcmp_mock.call_count, 0)

        #Test 2: parse crypt file already updated
        exists_mock.reset_mock()
        fcmp_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.return_value = True
        fcmp_mock.return_value = True
        self.rh_patching.update_crypt_parse_file()
        self.assertEqual(exists_mock.call_count, 1)
        self.assertEqual(fcmp_mock.call_count, 1)
        self.assertEqual(ce_mock.call_count, 0)

        #Test 3: ADE parameters not present in grub
        exists_mock.reset_mock()
        fcmp_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.return_value = True
        fcmp_mock.return_value = False
        ce_mock.return_value = 1
        self.rh_patching.update_crypt_parse_file()
        self.assertEqual(exists_mock.call_count, 1)
        self.assertEqual(fcmp_mock.call_count, 1)
        self.assertEqual(ce_mock.call_count, 1)
        self.assertEqual(pcs_mock.call_count, 0)

        #Test 4: default grub does not have duplicate ADE entries
        exists_mock.reset_mock()
        fcmp_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.return_value = True
        fcmp_mock.return_value = False
        ce_mock.return_value = 0
        pcs_mock.stdout = "1"
        self.rh_patching.update_crypt_parse_file(proc_comm=pcs_mock)
        self.assertEqual(exists_mock.call_count, 1)
        self.assertEqual(fcmp_mock.call_count, 1)
        self.assertEqual(ce_mock.call_count, 1)
        self.assertEqual(scf_mock.call_count, 0)

        #TODO: Add success case unittest. Need to resolve import error for redhatPatching