#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2015 Microsoft Corporation
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

from collections import namedtuple

class OSEncryptionState(object):
    def __init__(self, context):
        super(OSEncryptionState, self).__init__()
        self.context = context
        self.state_executed = False

    def enter(self):
        assert 0, "implement enter"

    def should_exit(self):
        assert 0, "implement should_exit"

OSEncryptionStateContext = namedtuple('OSEncryptionStateContext',
                                      ['hutil',
                                       'distro_patcher',
                                       'logger',
                                       'encryption_environment'])
