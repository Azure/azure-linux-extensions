#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation  
# All rights reserved.   
# MIT License  
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.  
import Utils.XmlUtil as XmlUtil

# Try to get the Application Insights key from LadCfg.
def tryGetAiKey(ladCfg):
    if not ladCfg:
        return
    if not 'sinksConfig' in ladCfg:
        return
    sinksConfig = ladCfg['sinksConfig']
    if not 'sinks' in sinksConfig:
        return
    sinks = sinksConfig['sinks']
    list = [s for s in sinks if "applicationInsights" in s];
    if not list or len(list) < 1:
        return
    ai = list[0];
    return ai["applicationInsights"]

def createAccountElement(mdsdCfg, aikey):
    aiAccountElement = XmlUtil.createElement("<Account moniker=\"appinsights\" appInsightsKey=\"" + aikey + "\"/>");
    XmlUtil.addElement(mdsdCfg,'Accounts',aiAccountElement)

def createSyslogRouteEventElement(mdsdCfg):
    aiSyslogRouteEvent = XmlUtil.createElement("<RouteEvent eventName=\"aiSyslogRouteEvent\" priority=\"High\" account=\"appinsights\" storeType=\"appinsights\"/>");
    XmlUtil.addElement(mdsdCfg,'Events/MdsdEvents/MdsdEventSource',aiSyslogRouteEvent,['source','syslog'])

def updateOMIQueryElement(omiQueryElement):
    # Application Insights requires the event name for performance counters to end in "Stats".
    eventName = omiQueryElement.get('eventName')
    omiQueryElement.set('eventName',eventName + 'Stats')
    omiQueryElement.set('storeType','appinsights')
    omiQueryElement.set('account','appinsights')
