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
import customscript as cs
import blob as test_blob
import blob_mooncake as test_blob_mooncake

class TestBlobDownload(unittest.TestCase):
    def test_download_blob(self):
        download_dir = "/tmp"
        cs.download_and_save_blob(test_blob.name, 
                                  test_blob.key, 
                                  test_blob.uri,
                                  download_dir)
        
        cs.download_and_save_blob(test_blob_mooncake.name, 
                                  test_blob_mooncake.key, 
                                  test_blob_mooncake.uri,
                                  download_dir)

if __name__ == '__main__':
    unittest.main()
