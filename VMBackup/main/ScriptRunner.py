import json
import subprocess
import time
import os
from pwd import getpwuid
from stat import *
from common import CommonVariables
import traceback
from Utils import HandlerUtil

    # config.json --------structure---------
    # {
    #     "pluginName" : "oracleLinux",
    #     "timeoutInSeconds" : (in seconds),
    #     "continueBackupOnFailure" : true/false,
    #
    #     ... other config params ...
    #
    #     "preScriptLocation" : "/abc/xyz.sh"
    #     "postScriptLocation" : "/abc/def.sh"
    #     "preScriptNoOfRetries" : 3,
    #     "postScriptNoOfRetries" : 2,
    #     "preScriptParams" : [
    #         ... all params to be passed to prescript ...
    #     ],
    #     "postScriptParams" : [
    #         ... all params to be passed to postscript ...
    #     ]
    # }
    #
    #
    # errorcode policy
    # errorcode = 0 (CommonVariables.PrePost_PluginStatus_Successs), means success, script runs without error, warnings maybe possible
    # errorcode = 5 (CommonVariables.PrePost_PluginStatus_Timeout), means timeout
    # errorcode = 10 (CommonVariables.PrePost_PluginStatus_ConfigNotFound), config file not found
    # errorcode = process return code, means bash script encountered some other error, like 127 for script not found


class ScriptRunnerResult(object):
    def __init__(self):
        self.errorCode = None
        self.continueBackup = True
        self.noOfRetries = 0
        self.requiredNoOfRetries = 0
        self.fileCode = []
        self.filePath = []

    def __str__(self):
        errorStr =  'ErrorCode :- ' + str(self.errorCode) + '\n'
        errorStr += 'Continue Backup :- ' + str(self.continueBackup) + '\n'
        errorStr += 'Number of Retries done :- ' + str(self.noOfRetries) + '\n'
        return errorStr


class ScriptRunner(object):
    """ description of class """
    def __init__(self, logger, name, configPath, maxTimeOut):
        self.logger = logger
        self.timeoutInSeconds = 10
        self.pollSleepTime = 3
        self.pollTotalCount = (self.timeoutInSeconds / self.pollSleepTime)
        self.configLocation = configPath
        self.pluginName = name
        self.continueBackupOnFailure = True
        self.preScriptParams = []
        self.postScriptParams = []
        self.preScriptLocation = None
        self.postScriptLocation = None
        self.preScriptNoOfRetries = 0
        self.postScriptNoOfRetries = 0
        self.fsFreeze_on = True
        self.configLoaded = False
        self.PreScriptCompletedSuccessfully = False
        self.maxTimeOut = maxTimeOut

    def get_config(self):
        """
            Get configuration information from config.json

        """
        try:
            with open(self.configLocation, 'r') as configFile:
                configData = json.load(configFile)
            configDataKeys = configData.keys()
            if 'timeoutInSeconds' in configDataKeys:
                self.timeoutInSeconds = min(configData['timeoutInSeconds'],self.maxTimeOut)
            if 'pluginName' in configDataKeys:
                self.pluginName = configData['pluginName']
            if 'appName' in configDataKeys:
                HandlerUtil.HandlerUtility.add_to_telemetery_data('appName',configData['appName'])
            self.preScriptLocation = configData['preScriptLocation']
            self.postScriptLocation = configData['postScriptLocation']
            if 'preScriptParams' in configDataKeys:
                self.preScriptParams = configData['preScriptParams']
            if 'postScriptParams' in configDataKeys:
                self.postScriptParams = configData['postScriptParams']
            if 'continueBackupOnFailure' in configDataKeys:
                self.continueBackupOnFailure = configData['continueBackupOnFailure']
            if 'preScriptNoOfRetries' in configDataKeys:
                self.preScriptNoOfRetries = configData['preScriptNoOfRetries']
            if 'postScriptNoOfRetries' in configDataKeys:
                self.postScriptNoOfRetries = configData['postScriptNoOfRetries']
            if 'fsFreezeEnabled' in configDataKeys:
                self.fsFreeze_on = configData['fsFreezeEnabled']
            self.pollTotalCount = (self.timeoutInSeconds / self.pollSleepTime)
            self.configLoaded = True
        except IOError:
            errMsg = 'Error in opening ' + self.pluginName + ' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        except ValueError as err:
            errMsg = 'Error in decoding ' + self.pluginName + ' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        except KeyError as err:
            errMsg = 'Error in fetching value for the key '+str(err) + ' in ' +self.pluginName+' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')

    def find_owner(self, filename):
        file_owner = ''
        try:
            file_owner = getpwuid(os.stat(filename).st_uid).pw_name
        except Exception as err:
            errMsg = 'Error in fetching owner of the file : ' + filename  + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')

        return file_owner

    def validate_permissions(self, filename):
        valid_permissions = True
        try:
            permissions = oct(os.stat(filename)[ST_MODE])[-3:]
            self.logger.log('Permisisons  of the file ' + filename + ' are ' + permissions,True)
            if int(permissions[1]) > 0 : #validating permissions for group
                valid_permissions = False
            if int(permissions[2]) > 0 : #validating permissions for others
                valid_permissions = False
        except Exception as err:
            errMsg = 'Error in fetching permissions of the file : ' + filename  + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            valid_permissions = False

        return valid_permissions

    def validate_scripts(self):

        errorCode = CommonVariables.PrePost_PluginStatus_Success
        dobackup = True

        self.get_config()
        self.logger.log('Plugin:'+str(self.pluginName)+' timeout:'+str(self.timeoutInSeconds)+' pollTotalCount:'+str(self.pollTotalCount) +' preScriptParams:'+str(self.preScriptParams)+' postScriptParams:' + str(self.postScriptParams)+ ' continueBackupOnFailure:' + str(self.continueBackupOnFailure) + ' preScriptNoOfRetries:' + str(self.preScriptNoOfRetries) + ' postScriptNoOfRetries:' + str(self.postScriptNoOfRetries) + ' Global FS Freeze on :' + str(self.fsFreeze_on), True, 'Info')

        if not self.configLoaded:
            errorCode = CommonVariables.FailedPrepostPluginConfigParsing
            self.logger.log('Cant run prescript for '+self.pluginName+' . Config File error.', True, 'Error')
            return errorCode,dobackup,self.fsFreeze_on

        dobackup = self.continueBackupOnFailure

        if not os.path.isfile(self.preScriptLocation):
            self.logger.log('Prescript file does not exist in the location '+self.preScriptLocation, True, 'Error')
            errorCode = CommonVariables.FailedPrepostPreScriptNotFound
            return errorCode,dobackup,self.fsFreeze_on

        if not self.validate_permissions(self.preScriptLocation):
            self.logger.log('Prescript file does not have desired permissions ', True, 'Error')
            errorCode = CommonVariables.FailedPrepostPreScriptPermissionError
            return errorCode,dobackup,self.fsFreeze_on


        if not self.find_owner(self.preScriptLocation) == 'root':
            self.logger.log('The owner of the PreScript file ' + self.preScriptLocation + ' is ' + self.find_owner(self.preScriptLocation) + ' but not root', True, 'Error')
            errorCode = CommonVariables.FailedPrepostPreScriptPermissionError
            return errorCode,dobackup,self.fsFreeze_on

        if not os.path.isfile(self.postScriptLocation):
            self.logger.log('Postscript file does not exist in the location ' + self.postScriptLocation, True, 'Error')
            errorCode = CommonVariables.FailedPrepostPostScriptNotFound
            return errorCode,dobackup,self.fsFreeze_on

        if not self.validate_permissions(self.postScriptLocation):
            self.logger.log('Postscript file does not have desired permissions ', True, 'Error')
            errorCode = CommonVariables.FailedPrepostPostScriptPermissionError
            return errorCode,dobackup,self.fsFreeze_on

        if not self.find_owner(self.postScriptLocation) == 'root':
            self.logger.log('The owner of the PostScript file ' + self.postScriptLocation + ' is '+ self.find_owner(self.postScriptLocation) + ' but  not root', True, 'Error')
            errorCode = CommonVariables.FailedPrepostPostScriptPermissionError
            return errorCode,dobackup,self.fsFreeze_on

        return errorCode,dobackup,self.fsFreeze_on

    def pre_script(self, pluginIndex, preScriptCompleted, preScriptResult):

            # Generates a system call to run the prescript
            # -- pluginIndex is the index for the current plugin assigned by pluginHost
            # -- preScriptCompleted is a bool array, upon completion of script, true will be assigned at pluginIndex
            # -- preScriptResult is an array and it stores the result at pluginIndex


        result = ScriptRunnerResult()
        result.requiredNoOfRetries = self.preScriptNoOfRetries

        paramsStr = ['sh',str(self.preScriptLocation)]
        for param in self.preScriptParams:
            paramsStr.append(str(param))

        self.logger.log('Running prescript for '+self.pluginName+' module...',True,'Info')
        process = subprocess.Popen(paramsStr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        flag_timeout = False
        curr = 0
        cnt = 0
        while True:
            while process.poll() is None:
                if curr >= self.pollTotalCount:
                    self.logger.log('Prescript for '+self.pluginName+' timed out.',True,'Error')
                    flag_timeout = True
                    break
                curr = curr + 1
                time.sleep(self.pollSleepTime)
            if process.returncode is CommonVariables.PrePost_ScriptStatus_Success:
                break
            if flag_timeout:
                break
            if cnt >= self.preScriptNoOfRetries:
                break
            self.logger.log('Prescript for '+self.pluginName+' failed. Retrying...',True,'Info')
            cnt = cnt + 1


        result.noOfRetries = cnt
        if not flag_timeout:
            result.errorCode = process.returncode
            if result.errorCode != CommonVariables.PrePost_ScriptStatus_Success and result.errorCode != CommonVariables.PrePost_ScriptStatus_Warning :
                self.logger.log('Prescript for '+self.pluginName+' failed with error code: '+str(result.errorCode)+' .',True,'Error')
                result.continueBackup = self.continueBackupOnFailure
                result.errorCode = CommonVariables.FailedPrepostPreScriptFailed
            else:
                self.PreScriptCompletedSuccessfully = True
                self.logger.log('Prescript for '+self.pluginName+' successfully executed.',True,'Info')
        else:
            result.errorCode =  CommonVariables.FailedPrepostPreScriptTimeout
            result.continueBackup = self.continueBackupOnFailure
        preScriptCompleted[pluginIndex] = True
        preScriptResult[pluginIndex] = result

    def post_script(self, pluginIndex, postScriptCompleted, postScriptResult):

            # Generates a system call to run the postscript
            # -- pluginIndex is the index for the current plugin assigned by pluginHost
            # -- postScriptCompleted is a bool array, upon completion of script, true will be assigned at pluginIndex
            # -- postScriptResult is an array and it stores the result at pluginIndex

        result = ScriptRunnerResult()

        if not self.PreScriptCompletedSuccessfully:
            self.logger.log('PreScript execution did not complete for ' + self.pluginName + '.Post Script is not triggered', True, 'Info')

        result.requiredNoOfRetries = self.postScriptNoOfRetries

        paramsStr = ['sh',str(self.postScriptLocation)]
        for param in self.postScriptParams:
            paramsStr.append(str(param))

        self.logger.log('Running postscript for '+self.pluginName+' module...',True,'Info')
        process = subprocess.Popen(paramsStr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        flag_timeout = False
        curr = 0
        cnt = 0
        while True:
            while process.poll() is None:
                if curr >= self.pollTotalCount:
                    self.logger.log('Postscript for '+self.pluginName+' timed out.',True,'Error')
                    flag_timeout = True
                    break
                curr = curr + 1
                time.sleep(self.pollSleepTime)
            if process.returncode is CommonVariables.PrePost_ScriptStatus_Success:
                break
            if flag_timeout:
                break
            if cnt >= self.postScriptNoOfRetries:
                break
            self.logger.log('Postscript for '+self.pluginName+' failed. Retrying...',True,'Info')
            cnt = cnt + 1

        result.noOfRetries = cnt
        if not flag_timeout:
            result.errorCode = process.returncode
            if result.errorCode != CommonVariables.PrePost_ScriptStatus_Success and result.errorCode != CommonVariables.PrePost_ScriptStatus_Warning :
                self.logger.log('Postscript for '+self.pluginName+' failed with error code: '+str(result.errorCode)+' .',True,'Error')
                result.errorCode = CommonVariables.FailedPrepostPostScriptFailed
                result.continueBackup = self.continueBackupOnFailure
            else:
                self.logger.log('Postscript for '+self.pluginName+' successfully executed.',True,'Info')
        else:
            result.errorCode =  CommonVariables.FailedPrepostPostScriptTimeout
            result.continueBackup = self.continueBackupOnFailure
        postScriptCompleted[pluginIndex] = True
        postScriptResult[pluginIndex] = result
