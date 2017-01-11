#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import re
from collections import defaultdict

def GetCounterSetting(counterSpec, name):
    if counterSpec.has_key(name):
        return counterSpec[name]
    return None

def IntervalToSeconds(specifiedInterval):
    interval = specifiedInterval.upper()
    if interval[0] != 'P':
        raise ValueError('Not an ISO8601 duration string')
    if interval[1] != 'T':
        raise ValueError('ISO8601 durations based on days or larger intervals are not supported')

    seconds = 0
    matches = re.findall(r'(\d+)(S|M|H)', interval[2:].upper())
    for qty, unit in matches:
        qty = int(qty)
        if unit == 'S':
            seconds += qty
        elif unit == 'M':
            seconds += qty * 60
        elif unit == 'H':
            seconds += qty * 3600

    if 0 == seconds:
        raise ValueError('Could not parse interval specification "{0}"'.format(specifiedInterval))
    return seconds

_EventNameUniquifiers = defaultdict(int)

def MakeUniqueEventName(prefix):
    _EventNameUniquifiers[prefix] += 1
    return '{0}{1:0>6}'.format(prefix, _EventNameUniquifiers[prefix])

class ParseException(Exception): pass

class UnexpectedCounterType(ParseException): pass

class InvalidCounterSpecification(ParseException): pass


