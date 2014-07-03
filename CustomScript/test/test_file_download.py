import unittest
import env
import handle
import os
import tempfile

class TestFileDownload(unittest.TestCase):
    def download_to_tmp(self, uri):
        tmpFile = tempfile.TemporaryFile()
        file_path = os.path.abspath(tmpFile.name)
        handle.download_and_save_file(uri, file_path)
        file_size = os.path.getsize(file_path)
        self.assertNotEqual(file_size, 0)
        tmpFile.close()
        os.unlink(tmpFile.name)
        
    def test_download_bin_file(self):
        uri = "http://www.bing.com/rms/Homepage$HPBottomBrand_default/ic/1f76acf2/d3a8cfeb.png"
        self.download_to_tmp(uri)

    def test_download_text_file(self):
        uri = "http://www.bing.com/"
        self.download_to_tmp(uri)

if __name__ == '__main__':
    unittest.main()
