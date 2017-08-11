#!/usr/bin/env python

"""
Handler library for Linux IaaS

JSON def:
HandlerEnvironment.json
[{
  "name": "ExampleHandlerLinux",
  "seqNo": "seqNo",
  "version": "1.0",
  "handlerEnvironment": {
    "logFolder": "<your log folder location>",
    "configFolder": "<your config folder location>",
    "statusFolder": "<your status folder location>",
    "heartbeatFile": "<your heartbeat file location>",
    
  }
}]

{
   "handlerSettings": 
  {
    "protectedSettings": 
    {
      "Password": "UserPassword"
        },
       "publicSettings": 
    {	
      "UserName": "UserName",
      "Expiration": "Password expiration date in yyy-mm-dd"
	}
  }
 }

Example ./config/1.settings
"{"runtimeSettings":[{"handlerSettings":{"protectedSettingsCertThumbprint":"1BE9A13AA1321C7C515EF109746998BAB6D86FD1","protectedSettings":
"MIIByAYJKoZIhvcNAQcDoIIBuTCCAbUCAQAxggFxMIIBbQIBADBVMEExPzA9BgoJkiaJk/IsZAEZFi9XaW5kb3dzIEF6dXJlIFNlcnZpY2UgTWFuYWdlbWVudCBmb3IgR+nhc6VHQTQpCiiV2zANBgkqhkiG9w0BAQEFAASCAQCKr09QKMGhwYe+O4/a8td+vpB4eTR+BQso84cV5KCAnD6iUIMcSYTrn9aveY6v6ykRLEw8GRKfri2d6tvVDggUrBqDwIgzejGTlCstcMJItWa8Je8gHZVSDfoN80AEOTws9Fp+wNXAbSuMJNb8EnpkpvigAWU2v6pGLEFvSKC0MCjDTkjpjqciGMcbe/r85RG3Zo21HLl0xNOpjDs/qqikc/ri43Y76E/Xv1vBSHEGMFprPy/Hwo3PqZCnulcbVzNnaXN3qi/kxV897xGMPPC3IrO7Nc++AT9qRLFI0841JLcLTlnoVG1okPzK9w6ttksDQmKBSHt3mfYV+skqs+EOMDsGCSqGSIb3DQEHATAUBggqhkiG9w0DBwQITgu0Nu3iFPuAGD6/QzKdtrnCI5425fIUy7LtpXJGmpWDUA==","publicSettings":{"port":"3000"}}}]}"


Example HeartBeat
{
"version": 1.0,
    "heartbeat" : {
        "status": "ready",
        "code": 0,
        "Message": "Sample Handler running. Waiting for a new configuration from user."
    }
}
Status uses either non-localized 'message' or localized 'formattedMessage' but not both.
{
    "version": 1.0,
    "timestampUTC": "<current utc time>",
    "status" : {
        "name": "<Handler workload name>",
        "operation": "<name of the operation being performed>",
        "configurationAppliedTime": "<UTC time indicating when the configuration was last successfully applied>",
        "status": "<transitioning | error | success | warning>",
        "code": <Valid integer status code>,
        "message": {
            "id": "id of the localized resource",
            "params": [
                "MyParam0",
                "MyParam1"
            ]
        },
        "formattedMessage": {
            "lang": "Lang[-locale]",
            "message": "formatted user message"
        }
    }
}
"""


import os
import sys
import imp
import base64
import json
import time

# waagent has no '.py' therefore create waagent module import manually.
waagent=imp.load_source('waagent','/usr/sbin/waagent')
def doParse(Log,operation):
    handler_env=None
    config=None
    ctxt=None
    code=0
    
    # get the HandlerEnvironment.json. it should always be in ./
    waagent.Log('cwd is ' + os.path.realpath(os.path.curdir))
    handler_env_file='./HandlerEnvironment.json'
    if not os.path.isfile(handler_env_file):
        waagent.Error("Unable to locate " + handler_env_file)
        sys.exit(1)
    ctxt=waagent.GetFileContents(handler_env_file)
    if ctxt == None :
        waagent.Error("Unable to read " + handler_env_file)    
    try:
        handler_env=json.loads(ctxt)
    except:
        pass
    if handler_env == None :
        waagent.Error("JSON error processing " + handler_env_file)    
        sys.exit(1)
    if type(handler_env) == list:
        handler_env = handler_env[0]
    
    # parse the dirs
    name='NULL'
    seqNo='0'
    version='0.0'
    config_dir='./'
    log_dir='./'
    status_dir='./'
    heartbeat_file='NULL.log'
    
    name=handler_env['name']
    seqNo=handler_env['seqNo']
    version=str(handler_env['version'])
    config_dir=handler_env['handlerEnvironment']['configFolder']
    log_dir=handler_env['handlerEnvironment']['logFolder']
    status_dir=handler_env['handlerEnvironment']['statusFolder']
    heartbeat_file=handler_env['handlerEnvironment']['heartbeatFile']
    
    # always get the newest settings file
    code,settings_file=waagent.RunGetOutput('ls -rt ' + config_dir + '/*.settings | tail -1')
    if code != 0:
        waagent.Error("Unable to locate a .settings file!")
        sys.exit(1)
    settings_file=settings_file[:-1]
    # get our incarnation # from the number of the .settings file
    incarnation=os.path.splitext(os.path.basename(settings_file))[0]
    waagent.Log('Incarnation is ' + incarnation)
    status_file=status_dir+'/'+incarnation+'.status'
    waagent.Log("setting file path is" + settings_file)
    ctxt=None
    ctxt=waagent.GetFileContents(settings_file)
    if ctxt == None :
        waagent.Error('Unable to read ' + settings_file + '. ')    
        doExit(name,seqNo,version,1,status_file,heartbeat_file,operation,'error','1', operation+' Failed', 'Read .settings', 'error', '1','Unable to read ' + settings_file + '. ','NotReady','1','Exiting')
    waagent.Log("Read: " + ctxt)
    # parse json
    config = None
    try:
        config=json.loads(ctxt)
    except:
        waagent.Error('JSON exception decoding ' + ctxt)
        
    if config == None:
        waagent.Error("JSON error processing " + settings_file)
        return (name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config)
    
#        doExit(name,seqNo,version,1,status_file,heartbeat_file,operation,'errior','1', operation + ' Failed', 'Parse Config', 'error', '1', 'JSON error processing ' + settings_file,'NotReady','1','Exiting')
 #       sys.exit(1)
    print repr(config)
    if config['runtimeSettings'][0]['handlerSettings'].has_key('protectedSettings') == True:
        thumb=config['runtimeSettings'][0]['handlerSettings']['protectedSettingsCertThumbprint']
        cert=waagent.LibDir+'/'+thumb+'.crt'
        pkey=waagent.LibDir+'/'+thumb+'.prv'
        waagent.SetFileContents('/tmp/kk',config['runtimeSettings'][0]['handlerSettings']['protectedSettings'])
        cleartxt=None
        cleartxt=waagent.RunGetOutput("base64 -d /tmp/kk | openssl smime  -inform DER -decrypt -recip " +  cert + "  -inkey " + pkey )[1]
        if cleartxt == None:
            waagent.Error("OpenSSh decode error using  thumbprint " + thumb )    
            doExit(name,seqNo,version,1,status_file,heartbeat_file,operation,'errior','1', operation + ' Failed', 'Parse Config', 'error', '1', 'OpenSsh decode error  using  thumbprint ' + thumb,'NotReady','1','Exiting')
            sys.exit(1)
        jctxt=''
        try:
            jctxt=json.loads(cleartxt)
        except:
            waagent.Error('JSON exception decoding ' + cleartxt)
        config['runtimeSettings'][0]['handlerSettings']['protectedSettings']=jctxt
        waagent.Log('Config decoded correctly.')

    return (name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config)


def doStatusReport(name,seqNo,version,stat_file,current_utc, started_at_utc, workload_name, operation_name, status, status_code, status_message, sub_workload_name, sub_status, sub_status_code, sub_status_message):
    #'{"handlerName":"Chef.Bootstrap.WindowsAzure.ChefClient","handlerVersion":"11.12.0.0","status":"NotReady","code":1,"formattedMessage":{"lang":"en-US","message":"Enable command of plugin (name: Chef.Bootstrap.WindowsAzure.ChefClient, version 11.12.0.0) failed with exception Command C:/Packages/Plugins/Chef.Bootstrap.WindowsAzure.ChefClient/11.12.0.0/enable.cmd of Chef.Bootstrap.WindowsAzure.ChefClient has exited with Exit code: 1"}},{"handlerName":"Microsoft.Compute.BGInfo","handlerVersion":"1.1","status":"Ready","formattedMessage":{"lang":"en-US","message":"plugin (name: Microsoft.Compute.BGInfo, version: 1.1) enabled successfully."}}'

    stat_rept='{"handlerName":"' + name + '","handlerVersion":"'+version+ '","status":"' +status + '","code":' + status_code + ',"formattedMessage":{"lang":"en-US","message":"' + status_message + '"}}'
    cur_file=stat_file+'_current'
    with open(cur_file,'w+') as f:
        f.write(stat_rept)
    # if inc.status exists, rename the inc.status to inc.status_sent
    if os.path.exists(stat_file) == True:
        os.rename(stat_file,stat_file+'_sent')
    # rename inc.status_current to inc.status
    os.rename(cur_file,stat_file)
    # remove  inc.status_sent
    if os.path.exists(stat_file+'_sent') == True:
        os.unlink(stat_file+'_sent')
        

def doHealthReport(heartbeat_file,status,code,message):
    # heartbeat
    health_report='[{"version":"1.0","heartbeat":{"status":"' + status+ '","code":"'+ code + '","Message":"' + message + '"}}]'
    if waagent.SetFileContents(heartbeat_file,health_report) == None :
        waagent.Error('Unable to wite heartbeat info to ' + heartbeat_file)    

def doExit(name,seqNo,version,exit_code,status_file,heartbeat_file,operation,status,code,message,sub_operation,sub_status,sub_code,sub_message,health_state,health_code,health_message):
    doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,
                   operation,status,code,message,sub_operation,sub_status,sub_code,sub_message)
    doHealthReport(heartbeat_file,'NotReady','1','Exiting')
    sys.exit(exit_code)

