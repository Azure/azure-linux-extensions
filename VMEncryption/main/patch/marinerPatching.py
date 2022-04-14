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