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

    def _mock_open_with_read_data_dict(self, open_mock, read_data_dict):
        open_mock.content_dict = read_data_dict

        def _open_side_effect(filename, mode, *args, **kwargs):
            read_data = open_mock.content_dict.get(filename)
            mock_obj = mock.mock_open(read_data=read_data)
            handle = mock_obj.return_value

            def write_handle(data, *args, **kwargs):
                if 'a' in mode:
                    open_mock.content_dict[filename] += data
                else:
                    open_mock.content_dict[filename] = data

            def write_lines_handle(data, *args, **kwargs):
                if 'a' in mode:
                    open_mock.content_dict[filename] += "".join(data)
                else:
                    open_mock.content_dict[filename] = "".join(data)
            handle.write.side_effect = write_handle
            handle.writelines.side_effect = write_lines_handle
            return handle

        open_mock.side_effect = _open_side_effect

    @mock.patch('time.sleep') # To speed up this test.
    @mock.patch('os.path.isfile', return_value=True)
    @mock.patch('main.EncryptionSettingsUtil.EncryptionSettingsUtil.get_http_util')
    def test_post_to_wire_server(self, get_http_util, os_path_isfile,  time_sleep):
        get_http_util.return_value = mock.MagicMock() # Return a mock object
        data = {"Protectors" : "mock data"}

        get_http_util.return_value.Call.return_value.status = 500 # make it so that the http call returns a 500
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)

        get_http_util.return_value.Call.reset_mock()

        get_http_util.return_value.Call.return_value.status = 400 # make it so that the http call returns a 400
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)

        get_http_util.return_value.Call.reset_mock()

        get_http_util.return_value.Call.return_value.status = 200 # make it so that the http call returns a 200
        self.es_util.post_to_wireserver(data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 1)

        get_http_util.return_value.Call.reset_mock()

        get_http_util.return_value.Call.return_value = None # Make it so that the HTTP call returns nothing
        self.assertRaises(Exception, self.es_util.post_to_wireserver, data)
        self.assertEqual(get_http_util.return_value.Call.call_count, 3)

    @mock.patch('os.path.exists')
    @mock.patch('__builtin__.open')
    def test_get_wireserver_endpoint_uri_valid_ip(self, open_mock, exists_mock):
        exists_mock.return_value = True
        self._mock_open_with_read_data_dict(open_mock, {Common.CommonVariables.wireserver_endpoint_file: '1.2.3.4'})
        endpoint_uri = self.es_util.get_wireserver_endpoint_uri()
        expected_endpoint_uri = 'http://1.2.3.4' + Common.CommonVariables.wireserver_endpoint_uri
        self.assertEqual(endpoint_uri, expected_endpoint_uri)

    @mock.patch('os.path.exists')
    @mock.patch('__builtin__.open')
    def test_get_wireserver_endpoint_uri_invalid_ip(self, open_mock, exists_mock):
        exists_mock.return_value = True
        self._mock_open_with_read_data_dict(open_mock, {Common.CommonVariables.wireserver_endpoint_file: '12.34'})
        endpoint_uri = self.es_util.get_wireserver_endpoint_uri()
        expected_endpoint_uri = 'http://' + Common.CommonVariables.static_wireserver_IP + Common.CommonVariables.wireserver_endpoint_uri
        self.assertEqual(endpoint_uri, expected_endpoint_uri)

    @mock.patch('os.path.exists')
    def test_get_wireserver_endpoint_uri_no_endpoint_file(self, exists_mock):
        exists_mock.return_value = False
        endpoint_uri = self.es_util.get_wireserver_endpoint_uri()
        expected_endpoint_uri = 'http://' + Common.CommonVariables.static_wireserver_IP + Common.CommonVariables.wireserver_endpoint_uri
        self.assertEqual(endpoint_uri, expected_endpoint_uri)
