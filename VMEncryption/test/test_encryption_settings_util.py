import unittest
import mock
from main import EncryptionSettingsUtil
from main import Common
from StringIO import StringIO
import console_logger

class TestEncryptionSettingsUtil(unittest.TestCase):
    """ unit tests for functions in the check_util module """
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.es_util = EncryptionSettingsUtil.EncryptionSettingsUtil(self.logger)

    @mock.patch('time.sleep') # To speed up this test.
    @mock.patch('main.EncryptionSettingsUtil.EncryptionSettingsUtil.write_settings_file')
    @mock.patch('main.EncryptionSettingsUtil.EncryptionSettingsUtil.get_index')
    @mock.patch('os.path.isfile', return_value=True)
    @mock.patch('main.EncryptionSettingsUtil.EncryptionSettingsUtil.get_http_util')
    def test_post_to_wire_server(self, get_http_util, os_path_isfile, get_index, write_settings_file, time_sleep):
        get_http_util.return_value = mock.MagicMock() # Return a mock object
        get_http_util.return_value.Call.return_value = None # Make it so that the HTTP call returns nothing
        get_index.return_value = 0
        data = {}
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)
        write_settings_file.assert_called_once()

