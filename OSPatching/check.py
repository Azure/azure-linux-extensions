#!/usr/bin/python
#
# OSPatching extension
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
import datetime


def main():
    intervalOfWeeks = int(sys.argv[1])
    if intervalOfWeeks == 1:
        sys.exit(0)

    history_scheduled = os.path.join(os.path.dirname(sys.argv[0]),
                                     'scheduled/history')
    today = datetime.date.today()
    today_dayOfWeek = today.strftime('%a')

    last_scheduled_date = None
    with open(history_scheduled) as f:
        lines = f.readlines()
        lines.reverse()
        for line in lines:
            line = line.strip()
            if line.endswith(today_dayOfWeek):
                last_scheduled_date = datetime.datetime.strptime(line,
                                                                 '%Y-%m-%d %a')
                break

    if (last_scheduled_date is not None and last_scheduled_date.date() +
            datetime.timedelta(days=intervalOfWeeks*7) > today):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
