#!/usr/bin/env python
#
# Azure Linux extension
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
# Requires Python 2.6+
#
import  xml.etree.ElementTree  as ET

def setXmlValue(xml,path,property,value,selector=[]):
    elements = xml.findall(path)
    for element in elements:
        if selector and element.get(selector[0])!=selector[1]:
            continue
        if not property:
            element.text = value
        elif not element.get(property) or len(element.get(property))==0 :
            element.set(property,value)

def getXmlValue(xml,path,property):
    element = xml.find(path)
    return element.get(property)

def addElement(xml,path,el,selector=[]):
    elements = xml.findall(path)
    for element in elements:
        if selector and element.get(selector[0])!=selector[1]:
            continue
        element.append(el)

def createElement(schema):
    return ET.fromstring(schema)

