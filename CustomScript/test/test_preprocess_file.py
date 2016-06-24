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
import zipfile
import codecs
import shutil

from MockUtil import MockUtil
import customscript as cs

class TestPreprocessFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            os.remove('master.zip')
            shutil.rmtree('encoding')
        except:
            pass
        os.system('wget https://github.com/bingosummer/scripts/archive/master.zip')
        zipFile = zipfile.ZipFile('master.zip')
        zipFile.extractall()
        zipFile.close()
        shutil.move('scripts-master', 'encoding')

    def test_bin_file(self):
        print("\nTest: Is it a binary file")
        file_path = "encoding/mslogo.png"
        self.assertFalse(cs.is_text_file(file_path)[0])

    def test_text_file(self):
        print("\nTest: Is it a text file")
        files = [file for file in os.listdir('encoding') if file.endswith('py') or file.endswith('sh') or file.endswith('txt')]
        for file in files:
            file_path = os.path.join('encoding', file)
            try:
                self.assertTrue(cs.is_text_file(file_path)[0])
            except:
                print(file)
                raise

    def test_bom(self):
        print("\nTest: Remove BOM")
        hutil = MockUtil(self)
        files = [file for file in os.listdir('encoding') if 'bom' in file]
        for file in files:
            file_path = os.path.join('encoding', file)
            cs.preprocess_files(file_path, hutil)
            with open(file_path, 'r') as f:
                contents = f.read()
            if "utf8" in file:
                self.assertFalse(contents.startswith(codecs.BOM_UTF8))
            if "utf16_le" in file:
                self.assertFalse(contents.startswith(codecs.BOM_LE))
            if "utf16_be" in file:
                self.assertFalse(contents.startswith(codecs.BOM_BE))

    def test_windows_line_break(self):
        print("\nTest: Convert text files from DOS to Unix formats")
        hutil = MockUtil(self)
        files = [file for file in os.listdir('encoding') if 'dos' in file]
        for file in files:
            file_path = os.path.join('encoding', file)
            cs.preprocess_files(file_path, hutil)
            with open(file_path, 'r') as f:
                contents = f.read()
            self.assertFalse("\r\n" in contents)

if __name__ == '__main__':
    unittest.main()
