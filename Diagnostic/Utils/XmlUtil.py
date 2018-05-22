#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation  
# All rights reserved.   
# MIT License  
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the ""Software""), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
#  the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
#  WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
#  OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import xml.etree.ElementTree as ET


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
    if element is not None:
        return element.get(property)


def addElement(xml,path,el,selector=[],addOnlyOnce=False):
    elements = xml.findall(path)
    for element in elements:
        if selector and element.get(selector[0])!=selector[1]:
            continue
        element.append(el)
        if addOnlyOnce:
            return


def createElement(schema):
    return ET.fromstring(schema)


def removeElement(tree, parent_path, removed_element_name):
    parents = tree.findall(parent_path)
    for parent in parents:
        element = parent.find(removed_element_name)
        while element is not None:
            parent.remove(element)
            element = parent.find(removed_element_name)