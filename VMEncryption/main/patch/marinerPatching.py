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
        self.grub_cfg_paths = [
            ("/boot/grub2/grub.cfg", "/boot/grub2/grubenv")
        ]

    def pack_initial_root_fs(self):
        self.command_executor.ExecuteInBash('mkinitrd -f -v', True)

    def add_kernelopts(self, args_to_add):
        self.add_args_to_default_grub(args_to_add)
        grub_cfg_paths = filter(lambda path_pair: os.path.exists(path_pair[0]) and os.path.exists(path_pair[1]), self.grub_cfg_paths)

        for grub_cfg_path, grub_env_path in grub_cfg_paths:
            for arg in args_to_add:
                self.command_executor.ExecuteInBash("grubby --args {0} --update-kernel ALL -c {1} --env={2}".format(arg, grub_cfg_path, grub_env_path))
