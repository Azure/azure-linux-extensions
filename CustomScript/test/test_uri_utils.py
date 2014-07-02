import unittest
import env
import handle

class TestUriUtils(unittest.TestCase):

    def test_get_path_from_uri(self):
        uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        path = handle.get_path_from_uri(uri)
        self.assertEqual(path, "/vhds/abc.sh")

    def test_get_blob_name_from_uri(self):
        uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        blob = handle.get_blob_name_from_uri(uri)
        self.assertEqual(blob, "abc.sh")

    def test_get_container_name_from_uri(self):
        uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        container = handle.get_container_name_from_uri(uri)
        self.assertEqual(container, "vhds")

if __name__ == '__main__':
    unittest.main()
