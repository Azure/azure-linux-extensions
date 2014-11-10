#!/usr/bin/env python
#
# VM Encryption extension
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
#
# Requires Python 2.7+
#
import subprocess
import sys
import urllib2
import urlparse
import httplib
from subprocess import *
import sys
import uuid
import time
#import chilkat

class KeyManager(object):
    def __init__(self, storageSASUri,password):
        file_name = 'tmpfs_' + str(uuid.uuid4())

        commandToExecute = '/bin/bash -c "mkdir /' + file_name + ' 2> /dev/null"'
        print(commandToExecute)
        proc = Popen(commandToExecute, shell=True)
        returnCode = proc.wait()

        commandToExecute = '/bin/bash -c "mount tmpfs /' + file_name + ' -t tmpfs -o size=10M ' + '2> /dev/null"'
        #TODO: handle the error case that the tmpfs not mount due to out of memory or other reason.
        print(commandToExecute)
        proc = Popen(commandToExecute, shell=True)
        returnCode = proc.wait()
        time.sleep( 5 )
        cert_file_path = '/' + file_name + '/cert.pfx'
        pem_file_path = '/' + file_name + '/cert.pem'
        self.download_and_save_file(storageSASUri, cert_file_path)

        #openssl pkcs12 -in /4658108b-c1f8-42c1-b58c-35b7321885d6/cert.pfx -clcerts -nokeys -out cert.pem -passin pass:User@123
        #' -out ' + pem_file_path +
        commandToExecute = '/bin/bash -c "openssl pkcs12  -clcerts -nokeys -in '+ cert_file_path +  ' -passin pass:' + password + '"'
        print(commandToExecute)
        proc = Popen(commandToExecute, shell=True, stdout = subprocess.PIPE)

        keyStream='';
        while True:
            line = proc.stdout.readline()
            keyStream += line.strip()
            print line
            if line == '' and proc.poll() != None:
                break
        returnCode = proc.wait()

        begin = keyStream.index("-----BEGIN CERTIFICATE-----")
        end = keyStream.index("-----END CERTIFICATE-----");
        self.key = keyStream[ begin+len("-----BEGIN CERTIFICATE-----") : end]

        print('key==' + self.key)
        #commandToExecute = '/bin/bash -c "umount /' + file_name + ' 2> /dev/null"'
        #print(commandToExecute)
        #proc = Popen(commandToExecute, shell=True)
        #returnCode = proc.wait()
    def getcert(self):

        pass
    def download_and_save_file(self, uri, file_path):
        src = urllib2.urlopen(uri)
        dest = open(file_path, 'wb')
        buf_size = 1024
        buf = src.read(buf_size)
        while(buf):
            dest.write(buf)
            buf = src.read(buf_size)
        # mount 
    #mount tmpfs <mountpoint> -t tmpfs -o size=2G
    #"""description of class"""
    #cert = chilkat.CkCert()

    ##  Load from the PFX file
    #pfxFilename = "/Users/chilkat/testData/pfx/chilkat_ssl_pwd_is_test.pfx"
    #pfxPassword = "test"

    ##  A PFX typically contains certificates in the chain of authentication.
    ##  The Chilkat cert object will choose the certificate w/
    ##  private key farthest from the root authority cert.
    ##  To access all the certificates in a PFX, use the
    ##  Chilkat certificate store object instead.
    
    #success = cert.LoadPfxFile(pfxFilename,pfxPassword)
    #if (success != True):
    #    print(cert.lastErrorText())
    #    sys.exit()

    ##  Get some information about the digital certificate,
    ##  then get the private key...

    ##  DN = "Distinguished Name"
    #print("SubjectDN:" + cert.subjectDN())

    #print("Common Name:" + cert.subjectCN())
    #print("Issuer Common Name:" + cert.issuerCN())

    #print("Serial Number:" + cert.serialNumber())

    ##  Now for the private key...

    ## privKey is a CkPrivateKey
    #privKey = cert.ExportPrivateKey()
    #if (privKey == None):
    #    print(cert.lastErrorText())
    #    sys.exit()