# Wrapper module for waagent
#
# waagent is not written as a module. This wrapper module is created 
# to use the waagent code as a module.
#
# Copyright (c) Microsoft Corporation  
# All rights reserved.   
# MIT License  
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.  
#
# Requires Python 2.7+
#


import imp
import os
import os.path

#
# The following code will search and load waagent code and expose
# it as a submodule of current module
#
def searchWAAgent():
    agentPath = '/usr/sbin/waagent'
    if(os.path.isfile(agentPath)):
        return agentPath
    user_paths = os.environ['PYTHONPATH'].split(os.pathsep)
    for user_path in user_paths:
        agentPath = os.path.join(user_path, 'waagent')
        if(os.path.isfile(agentPath)):
            return agentPath
    return None

agentPath = searchWAAgent()
if(agentPath):
    waagent = imp.load_source('waagent', agentPath)
else:
    raise Exception("Can't load waagent.")

if not hasattr(waagent, "AddExtensionEvent"):
    """
    If AddExtensionEvent is not defined, provide a dummy impl.
    """
    def _AddExtensionEvent(*args, **kwargs):
        pass
    waagent.AddExtensionEvent = _AddExtensionEvent

if not hasattr(waagent, "WALAEventOperation"):
    class _WALAEventOperation:
        HeartBeat="HeartBeat"
        Provision = "Provision"
        Install = "Install"
        UnIsntall = "UnInstall"
        Disable = "Disable"
        Enable = "Enable"
        Download = "Download"
        Upgrade = "Upgrade"
        Update = "Update"           
    waagent.WALAEventOperation = _WALAEventOperation

__ExtensionName__=None
def InitExtensionEventLog(name):
    __ExtensionName__=name

def AddExtensionEvent(name=__ExtensionName__,
                      op=waagent.WALAEventOperation.Enable, 
                      isSuccess=False, 
                      message=None):
    if name is not None:
        waagent.AddExtensionEvent(name=name,
                                  op=op,
                                  isSuccess=isSuccess,
                                  message=message)
