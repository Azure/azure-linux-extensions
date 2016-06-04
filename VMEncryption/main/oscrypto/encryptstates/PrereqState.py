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

from OSEncryptionState import *

class PrereqState(OSEncryptionState):
    def __init__(self, context):
        super(PrereqState, self).__init__(self)
        self.context = context
        self.state_executed = False

    def enter(self):
        if self.state_executed:
            return

        self.context.logger.log(">>>>> Entering prereq state")

    def should_exit(self):
        self.context.logger.log(">>>>> Verifying if machine should exit prereq state")
        self.state_executed = True

        return self.state_executed
