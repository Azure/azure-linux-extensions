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

import os


class SecondStageMarkConfig(object):
    """description of class"""
    def __init__(self):
        self.mark_file_path = './second_stage_mark_FD76C85E-406F-4CFA-8EB0-CF18B123365C'

    def MarkIt(self):
        with open(self.mark_file_path,'w') as file:
            file.write('marked')

    def IsMarked(self):
        return os.path.exists(self.mark_file_path)

    def ClearIt(self):
        if(self.IsMarked()):
            os.remove(self.mark_file_path)
        else:
            pass