#!/usr/bin/env python
#
#CustomScript extension
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import os
import tempfile
import customscript as cs

class TestFileDownload(unittest.TestCase):
    def test_download_blob(self):
        pass

    def download_to_tmp(self, uri):
        tmpFile = tempfile.TemporaryFile()
        file_path = os.path.abspath(tmpFile.name)
        cs.download_and_save_file(uri, file_path)
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
