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

import os
import unittest

import vmaccess
from Utils.WAAgentUtil import waagent

waagent.LoggerInit('/tmp/test.log','/dev/stdout')
waagent.MyDistro = waagent.GetMyDistro()

class Dummy(object):
    pass

hutil = Dummy()
hutil.log = waagent.Log

class TestCreateNewAccount(unittest.TestCase):
    def test_creat_newuser(self):
        settings={}
        settings['username'] = 'NewUser'
        settings['password'] = 'User@123'
        waagent.Run('userdel %s' %settings['username'])
        vmaccess._set_user_account_pub_key(settings, hutil)
        waagent.Run("echo 'exit' > /tmp/exit.sh")
        cmd_result = waagent.RunGetOutput("sshpass -p 'User@123' ssh -o StrictHostKeyChecking=no" 
                + " %s@localhost < /tmp/exit.sh" %settings['username'])
        self.assertEqual(cmd_result[0], 0)
        waagent.Run("rm exit.sh -f")
        waagent.Run('userdel %s' %settings['username'])

expected_cert_str = """\
-----BEGIN CERTIFICATE-----
MIICOTCCAaICCQD7F0nb+GtpcTANBgkqhkiG9w0BAQsFADBhMQswCQYDVQQGEwJh
YjELMAkGA1UECAwCYWIxCzAJBgNVBAcMAmFiMQswCQYDVQQKDAJhYjELMAkGA1UE
CwwCYWIxCzAJBgNVBAMMAmFiMREwDwYJKoZIhvcNAQkBFgJhYjAeFw0xNDA4MDUw
ODIwNDZaFw0xNTA4MDUwODIwNDZaMGExCzAJBgNVBAYTAmFiMQswCQYDVQQIDAJh
YjELMAkGA1UEBwwCYWIxCzAJBgNVBAoMAmFiMQswCQYDVQQLDAJhYjELMAkGA1UE
AwwCYWIxETAPBgkqhkiG9w0BCQEWAmFiMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCB
iQKBgQC4Vugyj4uAKGYHW/D1eAg1DmLAv01e+9I0zIi8HzJxP87MXmS8EdG5SEzR
N6tfQQie76JBSTYI4ngTaVCKx5dVT93LiWxLV193Q3vs/HtwwH1fLq0rAKUhREQ6
+CsRGNyeVfJkNsxAvNvQkectnYuOtcDxX5n/25eWAofobxVbSQIDAQABMA0GCSqG
SIb3DQEBCwUAA4GBAF20gkq/DeUSXkZA+jjmmbCPioB3KL63GpoTXfP65d6yU4xZ
TlMoLkqGKe3WoXmhjaTOssulgDAGA24IeWy/u7luH+oHdZEmEufFhj4M7tQ1pAhN
CT8JCL2dI3F76HD6ZutTOkwRar3PYk5q7RsSJdAemtnwVpgp+RBMtbmct7MQ
-----END CERTIFICATE-----
"""
class TestSaveCertFile(unittest.TestCase):
    def test_save_cert_Str_as_file(self):
        cert_str = waagent.GetFileContents(os.path.join(waagent.LibDir, 'TEST.crt'))
        vmaccess._save_cert_str_as_file(cert_str, '/tmp/tmp.crt')
        saved_cert_str = waagent.GetFileContents('/tmp/tmp.crt')
        self.assertEqual(saved_cert_str, expected_cert_str)

class TestResetSshKey(unittest.TestCase):
    def test_reset_ssh_key(self):
        settings={}
        settings['username'] = 'NewUser'
        settings['ssh_key'] = waagent.GetFileContents(os.path.join(waagent.LibDir, 'TEST.crt'))
        vmaccess._set_user_account_pub_key(settings, hutil)
        waagent.Run("echo 'exit' > /tmp/exit.sh")
        cmd_result = waagent.RunGetOutput("ssh -o StrictHostKeyChecking=no -i %s" %os.path.join(waagent.LibDir, 'TEST.prv')
                + " %s@localhost < /tmp/exit.sh" %settings['username'])
        self.assertEqual(cmd_result[0], 0)
        waagent.Run("rm exit.sh -f")
        waagent.Run('userdel %s' %settings['username'])


class TestResetExistingUser(unittest.TestCase):
    def test_reset_existing_user(self):
        settings={}
        settings['username'] = 'ExistingUser'
        settings['password'] = 'User@123'
        waagent.Run('userdel %s' %settings['username'])
        waagent.Run('useradd %s' %settings['username'])
        waagent.MyDistro.changePass(settings['username'], "Quattro!")
        vmaccess._set_user_account_pub_key(settings, hutil)
        waagent.Run("echo 'exit' > /tmp/exit.sh")
        cmd_result = waagent.RunGetOutput("sshpass -p 'User@123' ssh -o StrictHostKeyChecking=no" 
                + " %s@localhost < /tmp/exit.sh" %settings['username'])
        self.assertEqual(cmd_result[0], 0)
        waagent.Run("rm exit.sh -f")
        waagent.Run('userdel %s' %settings['username'])

if __name__ == '__main__':
    unittest.main()
