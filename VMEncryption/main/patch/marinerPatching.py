import os
import sys
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime
import subprocess
from .redhatPatching import redhatPatching
from Common import *

class marinerPatching(redhatPatching):
    def __init__(self,logger,distro_info):
        super(marinerPatching,self).__init__(logger,distro_info)
        self.logger = logger
        self.min_version_online_encryption = '2.0'
        self.support_online_encryption = self.validate_online_encryption_support()

    def patch_initial_root_fs(self):
        boot_dir = "/boot/"
        prev_n = "initramfs"
        new_n = "initrd"
        self.command_executor.ExecuteInBash("for file in {0}{1}*; do mv '$file' '${{file/{1}/{2}}}".format(boot_dir, prev_n, new_n))

    def add_kernelopts(self, args_to_add, grub_cfg_paths):
        grub_cfg_path = "/boot/grub2/grub.cfg"
        for arg in args_to_add:
            if "root=" in arg:
                self.command_executor.ExecuteInBash("sed -i 's!root=$rootdevice!{0}!'  '{1}'".format(arg, grub_cfg_path))
            else:
                self.command_executor.ExecuteInBash("sed -i '/mariner_linux/ s/$/ {0}/'  '{1}'".format(arg, grub_cfg_path))
