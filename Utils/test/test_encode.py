#!/usr/bin/env python
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


import Utils.extensionutils as eu
import unittest


class TestEncode(unittest.TestCase):
    def test_encode(self):
        contents = eu.get_file_contents('mock_sshd_config')
        encoded_contents = eu.encode_for_writing_to_file(contents)
        known_non_ascii_character = b"%c" % encoded_contents[2353]
        self.assertEqual(known_non_ascii_character, b'\x9d')

class TestRunCommandGetOutput(unittest.TestCase):
    def test_output(self):
        cmd = ["cat", "non_latin_characters.txt"]
        return_code, output_string = eu.run_command_get_output(cmd)
        self.assertEqual(0, return_code)
        expected_character_byte = b'\xc3\xbc'
        expected_character = expected_character_byte.decode("utf-8")
        self.assertEqual(expected_character, output_string[0])

    def test_stdin(self):
        cmd = ['bash', '-c', 'read ; echo $REPLY']
        cmd_input = b'\xc3\xbc' # ü character
        return_code, output_string = eu.run_send_stdin(cmd, cmd_input)
        self.assertEqual(0, return_code)
        self.assertEqual(cmd_input.decode('utf-8'), output_string[0])

if __name__ == '__main__':
    unittest.main()
