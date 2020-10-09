#
# Copyright 2020 Microsoft Corporation
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

import inspect
import os
import sys

scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
oscryptodir = os.path.abspath(os.path.join(scriptdir, '../../'))
sys.path.append(oscryptodir)

from .PrereqState import PrereqState
from .PatchBootSystemState import PatchBootSystemState
from .ResumeEncryptionState import ResumeEncryptionState
