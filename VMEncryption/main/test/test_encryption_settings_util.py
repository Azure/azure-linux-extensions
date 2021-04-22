import unittest
import EncryptionSettingsUtil
import Common
from io import StringIO
from .console_logger import ConsoleLogger
try:
    import unittest.mock as mock # python 3+ 
except ImportError:
    import mock # python2

class TestEncryptionSettingsUtil(unittest.TestCase):
    """ unit tests for functions in the check_util module """
    def setUp(self):
        self.logger = ConsoleLogger()
        self.es_util = EncryptionSettingsUtil.EncryptionSettingsUtil(self.logger)

    @mock.patch('time.sleep') # To speed up this test.
    @mock.patch('EncryptionSettingsUtil.EncryptionSettingsUtil.write_settings_file')
    @mock.patch('EncryptionSettingsUtil.EncryptionSettingsUtil.get_index')
    @mock.patch('os.path.isfile', return_value=True)
    @mock.patch('EncryptionSettingsUtil.EncryptionSettingsUtil.get_http_util')
    def test_post_to_wire_server(self, get_http_util, os_path_isfile, get_index, write_settings_file, time_sleep):
        get_http_util.return_value = mock.MagicMock() # Return a mock object
        get_index.return_value = 0
        data = {"Protectors" : "mock data"}

        get_http_util.return_value.Call.return_value.status = 500 # make it so that the http call returns a 500
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)
        self.assertEqual(write_settings_file.call_count, 0)

        get_http_util.return_value.Call.reset_mock()

        get_http_util.return_value.Call.return_value.status = 400 # make it so that the http call returns a 400
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)
        self.assertEqual(write_settings_file.call_count, 0)

        get_http_util.return_value.Call.reset_mock()

        get_http_util.return_value.Call.return_value.status = 200 # make it so that the http call returns a 200
        self.es_util.post_to_wireserver(data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 1)
        self.assertEqual(write_settings_file.call_count, 0)

        get_http_util.return_value.Call.reset_mock()

        get_http_util.return_value.Call.return_value = None # Make it so that the HTTP call returns nothing
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)
        self.assertEqual(write_settings_file.call_count, 0)

    def test_get_fault_reason_correct_xml(self):
        mock_error_xml = "<?xml version='1.0' encoding='utf-8'?>\
                          <Error xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xmlns:xsd='http://www.w3.org/2001/XMLSchema'>\
                          <Code>BadRequest</Code>\
                          <Message>The request contents are invalid or incomplete. Please refresh your resource cache and retry.</Message>\
                          <Details>The fault reason was: '  0xc1425072  RUNTIME_E_KEYVAULT_SET_SECRET_FAILED  Failed to set secret to KeyVault '.</Details></Error>"
        reason = self.es_util.get_fault_reason(mock_error_xml)
        self.assertEqual(reason, "The fault reason was: '  0xc1425072  RUNTIME_E_KEYVAULT_SET_SECRET_FAILED  Failed to set secret to KeyVault '.")

    def test_get_fault_reason_invalid_xml(self):
        mock_invalid_xml = "This is inavlid xml"
        reason = self.es_util.get_fault_reason(mock_invalid_xml)
        self.assertEqual(reason, "Unknown")

    def test_get_fault_reason_no_detail_element(self):
        mock_error_xml = "<?xml version='1.0' encoding='utf-8'?>\
                          <Error xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xmlns:xsd='http://www.w3.org/2001/XMLSchema'>\
                          <Code>BadRequest</Code>\
                          <Message>The request contents are invalid or incomplete. Please refresh your resource cache and retry.</Message></Error>"
        reason = self.es_util.get_fault_reason(mock_error_xml)
        self.assertEqual(reason, "Unknown")

    def test_get_fault_reason_no_detail_element_text(self):
        mock_error_xml = "<?xml version='1.0' encoding='utf-8'?>\
                          <Error xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xmlns:xsd='http://www.w3.org/2001/XMLSchema'>\
                          <Code>BadRequest</Code>\
                          <Message>The request contents are invalid or incomplete. Please refresh your resource cache and retry.</Message>\
                          <Details></Details></Error>"
        reason = self.es_util.get_fault_reason(mock_error_xml)
        self.assertEqual(reason, "Unknown")
