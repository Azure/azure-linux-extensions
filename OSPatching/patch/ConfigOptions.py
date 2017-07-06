#!/usr/bin/python
#
# AbstractPatching is the base patching class of all the linux distros
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


class ConfigOptions(object):
    disabled = ["true", "false"]             # Default value is "false"
    stop = ["true", "false"]                 # Default value is "false"
    reboot_after_patch = ["rebootifneed",    # Default value is "rebootifneed"
                          "auto",
                          "required",
                          "notrequired"]
    category = {"required" : "important",    # Default value is "important"
                "all"      : "importantandrecommended"}
    oneoff = ["true", "false"]               # Default value is "false"
    interval_of_weeks = [str(i) for i in range(1, 53)]  # Default value is "1"
    day_of_week = {"everyday" : range(1,8),  # Default value is "everyday"
                   "monday"   : 1,
                   "tuesday"  : 2,
                   "wednesday": 3,
                   "thursday" : 4,
                   "friday"   : 5,
                   "saturday" : 6,
                   "sunday"   : 7}
