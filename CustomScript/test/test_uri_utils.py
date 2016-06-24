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


class TestUriUtils(unittest.TestCase):
    def test_get_path_from_uri(self):
        uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        path = cs.get_path_from_uri(uri)
        self.assertEqual(path, "/vhds/abc.sh")

    def test_get_blob_name_from_uri(self):
        uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        blob = cs.get_blob_name_from_uri(uri)
        self.assertEqual(blob, "abc.sh")

    def test_get_container_name_from_uri(self):
        uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        container = cs.get_container_name_from_uri(uri)
        self.assertEqual(container, "vhds")

    def test_get_host_base_from_uri(self):
        blob_uri = "http://qingfu2.blob.core.windows.net/vhds/abc.sh?st=2014-06-27Z&se=2014-06-27&sr=c&sp=r&sig=KBwcWOx"
        host_base = cs.get_host_base_from_uri(blob_uri)
        self.assertEqual(host_base, ".blob.core.windows.net")
        blob_uri = "https://yue.blob.core.chinacloudapi.cn/"
        host_base = cs.get_host_base_from_uri(blob_uri)
        self.assertEqual(host_base, ".blob.core.chinacloudapi.cn")

if __name__ == '__main__':
    unittest.main()
