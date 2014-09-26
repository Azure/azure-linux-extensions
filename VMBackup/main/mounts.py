#!/usr/bin/env python
#
# VM Backup extension
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

from os.path import *

import re
import sys
import subprocess
import types

from StringIO import StringIO

class Error(Exception):
    pass

def is_mounted(dir):
    return Mounts().exists(realpath(dir))

def system(*args):
    error = subprocess.call(args)
    if error:
        raise Error("nonzero exitcode %d from command `%s'" % (error, " ".join(args)))

class Mount:
    def __init__(self, device, dir, type, opts):
        self.device = device
        self.dir = dir
        self.type = type
        self.opts = opts
        
    def mount(self, root):
        if self.is_mounted(root):
            return False
        
        if root:
            realdir = root + self.dir
        else:
            realdir = self.dir

        system("mount", "-t", self.type, "-o", self.opts, self.device, realdir)
        return True

    def umount(self, root):
        if not self.is_mounted(root):
            return False
        
        if root:
            realdir = root + self.dir
        else:
            realdir = self.dir
        system("umount", realdir)
        return True

    def is_mounted(self, root):
        if root:
            realdir = root + self.dir
        else:
            realdir = self.dir
        return is_mounted(realdir)

class Mounts:
    @staticmethod
    def _parse(fh, root):
        for line in fh.readlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            vals = re.split(r'\s+', line)
            if len(vals) < 4:
                continue

            device, dir, type, opts = vals[:4]
            if not dir.startswith("/"):
                dir = "/" + dir

            if root:
                # skip mounts that are not subdirectories of root
                if dir == root or not dir.startswith(root + "/"):
                    continue

                if root != "/":
                    dir = dir[len(root):]

            yield Mount(device, dir, type, opts)
            
    def __init__(self, root=None, fstab=None):
        """Initialize a list of mounts under <root> (defaults to /)

        By default we merge /etc/mtab and /proc/mounts, unless
        <fstab> is provided.

        <fstab> can be a file path, a file handle, or a string containing
        fstab-like values"""

        self.mounts = []
        if root:
            root = realpath(root)

        if fstab:
            if isinstance(fstab, file):
                fh = fstab
            else:
                fstab = str(fstab)
                if exists(fstab):
                    try:
                        fh = file(fstab)
                    except IOError, e:
                        raise Error(e)
                else:
                    fh = StringIO(fstab)

            for mount in self._parse(fh, root):
                self.mounts.append(mount)
        else:
            for mount in self._parse(file("/etc/mtab"), root):
                self.mounts.append(mount)

            for mount in self._parse(file("/proc/mounts"), root):
                if not self.exists(mount.dir):
                    self.mounts.append(mount)

        self.root = root

    def __len__(self):
        return len(self.mounts)
    
    def __str__(self):
        return "\n".join([ " ".join([mount.device, mount.dir, mount.type, mount.opts]) \
                           for mount in self.mounts ])
    
    def save(self, path):
        fh = file(path, "w")
        print >> fh, str(self)
        fh.close()

    def exists(self, dir):
        """Returns True if dir exists in mounts"""
        for mount in self.mounts:
            if mount.dir.rstrip("/") == dir.rstrip("/"):
                return True
        return False

    def mount(self, root=None):
        if root is None:
            root = self.root
            
        for mount in self.mounts:
            mount.mount(root)

    def umount(self, root=None):
        if root is None:
            root = self.root

        unmounted = []
        for mount in reversed(self.mounts):
            try:
                mount.umount(root)
            except:
                for mount in reversed(unmounted):
                    mount.mount(root)
                raise
            unmounted.append(mount)