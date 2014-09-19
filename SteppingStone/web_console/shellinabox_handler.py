#!/usr/bin/python
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
# Requires Python 2.4+


import os
import sys
import socket
import traceback
import subprocess
import random

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

from settings import *
from distro import *

class ShellinaboxHandler(object):
    def __init__(self, hutil):
        self.hutil = hutil
        self.installer = get_installer()
        self.from_pkg = True
        self.SHELLINABOX_CMD = '/usr/bin/shellinaboxd' if self.from_pkg else os.path.join(SHELLINABOX_PREFIX, 'bin/shellinaboxd')
        self.web_console_uri = dict()
        self.port_pool = self.get_available_ports()

        self.installer.install_pkg('build-essential')
        self.installer.install_pkg('openssl')

    def install(self):
        if self.from_pkg:
            self.install_from_pkg()
        else:
            self.install_from_source()

    def install_from_pkg(self):
        self.installer.install_pkg('shellinabox') # ubuntu 14.04
        self.installer.stop_shellinabox()

    def install_from_source(self):
        if not os.path.isfile(self.SHELLINABOX_CMD):
            curdir = os.getcwd()
            os.chdir(ROOT_DIR)
            self.hutil.log('Downloading shellinabox source into ' + ROOT_DIR)
            waagent.Run(' '.join(['wget --no-check-certificate', SHELLINABOX_DOWNLOAD_URI + SHELLINABOX_SRC + '.tar.gz']))
            waagent.Run(' '.join(['tar zxf', SHELLINABOX_SRC + '.tar.gz']))
            waagent.Run(' '.join(['rm -f', SHELLINABOX_SRC + '.tar.gz']))
            os.chdir(SHELLINABOX_SRC)
            waagent.Run('./configure --prefix=' + SHELLINABOX_PREFIX)
            waagent.Run('make && make install')
            os.chdir(curdir)
            self.hutil.log('Installing shellinabox: SUCCESS')
        else:
            self.hutil.log('shellinabox has been installed')

    def enable_local(self, disable_ssl, port):
        self.start(disable_ssl, 'localhost', port)

    def enable_stepping_stone(self, connections):
        for con in connections:
            if con['disabled']:
                port = self.stop(con['hostname'])
            else:
                self.start(con['disableSSL'], con['hostname'])

    def start(self, disable_ssl=False, hostname='localhost', port=-1):
        old_port = None
        if self.status(hostname) is not None:
            self.hutil.log('shellinabox is already running on ' + hostname)
            old_port = self.stop(hostname)
        if port == -1:
            if old_port is not None:
                port = old_port
            else:
                if self.port_pool:
                    port = random.sample(self.port_pool, 1)[0]
                else:
                    self.hutil.error('Failed to find any available port for ' + hostname)
                    return
        cmds = [self.SHELLINABOX_CMD]
        pid_file = '/var/run/' + '_'.join([hostname, 'http' if disable_ssl else 'https', str(port), 'shellinaboxd.pid'])
        cmds.extend(['-q', '--background='+pid_file, '-t' if disable_ssl else SHELLINABOX_CERT_DIR, '-p '+str(port), SHELLINABOX_CERT_OWNER, '-s /:SSH:'+hostname, SHELLINABOX_DEFAULT_OPTS])
        self.port_pool.remove(port)
        os.system(' '.join(cmds))
        self.hutil.log('Starting shellinabox on ' + hostname + ': SUCCESS')

    def stop(self, hostname='localhost'):
        pid_file = self.status(hostname)
        if pid_file is None:
            return None
        with open(pid_file) as f:
            pid = f.read()
        try:
            os.kill(int(pid), 9)
        except:
            pass
        if os.path.isfile(pid_file):
            os.remove(pid_file)
        self.hutil.log('Stopping shellinabox on ' + hostname + ': SUCCESS')
        port = int(pid_file.split('_')[-2])
        self.port_pool.append(port)
        return port

    def status(self, hostname='localhost'):
        file_list = os.listdir('/var/run')
        pid_file_suffix = 'shellinaboxd.pid'
        pid_file = [f for f in file_list if f.endswith(pid_file_suffix) and f.startswith(hostname)]
        if len(pid_file) == 0:
            return None
        return os.path.join('/var/run', pid_file[0])
        
    def get_web_console_uri(self):
        file_list = os.listdir('/var/run')
        pid_file_suffix = 'shellinaboxd.pid'
        pid_file_list = [f for f in file_list if f.endswith(pid_file_suffix)]
        for pid_file in pid_file_list:
            hostname = pid_file.split('_')[0]
            self.web_console_uri[hostname] = pid_file.split('_')[1] + '://' + socket.gethostname() + AZURE_VM_DOMAIN + ':' + pid_file.split('_')[2]
        return self.web_console_uri

    def get_available_ports(self):
        file_list = os.listdir('/var/run')
        pid_file_suffix = 'shellinaboxd.pid'
        pid_file_list = [f for f in file_list if f.endswith(pid_file_suffix)]
        port_pool = SHELLINABOX_PORT_RANGE
        for pid_file in pid_file_list:
            port_pool.remove(int(pid_file.split('_')[2]))
        return port_pool
