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
    list = [s for s in sinks if s["name"] == "ApplicationInsights"];
    if not list or len(list) < 1:
        return
    ai = list[0];
    if not 'instrumentationKey' in ai:
        return
    return ai["instrumentationKey"]

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
