import json
import subprocess
import time
import os
import errno
import threading
from common import CommonVariables
import traceback
from Utils import HandlerUtil
from Utils.PinnedScript import PinnedScript

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
        self._pinned_scripts = {}
        self._script_lock = threading.Lock()

    def close(self):
        """Release validation handles, including when the post-script is skipped."""
        with self._script_lock:
            for script in self._pinned_scripts.values():
                script.close()
            self._pinned_scripts.clear()

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
            if 'ScriptsExecutionPollTimeSeconds' in configDataKeys and int(configData['ScriptsExecutionPollTimeSeconds']) >= 1 and int(configData['ScriptsExecutionPollTimeSeconds']) <=5:
                self.pollSleepTime = int(configData['ScriptsExecutionPollTimeSeconds'])
            self.pollTotalCount = (self.timeoutInSeconds / self.pollSleepTime)
            self.configLoaded = True
        except IOError as err:
            errMsg = 'Error in opening ' + self.pluginName + ' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        except ValueError as err:
            errMsg = 'Error in decoding ' + self.pluginName + ' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        except KeyError as err:
            errMsg = 'Error in fetching value for the key '+str(err) + ' in ' +self.pluginName+' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')

    def validate_scripts(self):

        errorCode = CommonVariables.PrePost_PluginStatus_Success
        dobackup = True

        self.close()
        self.configLoaded = False
        self.PreScriptCompletedSuccessfully = False
        self.get_config()
        self.logger.log(
            'Plugin {0}: timeout={1}, continueBackupOnFailure={2}, fsFreeze={3}'.format(
                self.pluginName, self.timeoutInSeconds,
                self.continueBackupOnFailure, self.fsFreeze_on), True, 'Info')

        if not self.configLoaded:
            errorCode = CommonVariables.FailedPrepostPluginConfigParsing
            self.logger.log('Cant run prescript for '+self.pluginName+' . Config File error.', True, 'Error')
            return errorCode,dobackup,self.fsFreeze_on, self.pollSleepTime

        dobackup = self.continueBackupOnFailure

        scripts = [
            ('pre', self.preScriptLocation,
             CommonVariables.FailedPrepostPreScriptNotFound,
             CommonVariables.FailedPrepostPreScriptPermissionError),
            ('post', self.postScriptLocation,
             CommonVariables.FailedPrepostPostScriptNotFound,
             CommonVariables.FailedPrepostPostScriptPermissionError)]
        for stage, path, not_found, permission_error in scripts:
            try:
                # Validate the open object, then retain it across snapshot.
                self._pinned_scripts[stage] = PinnedScript(path, self.logger)
                self._pinned_scripts[stage].execution_path()
            except (OSError, AttributeError) as err:
                missing_script = (getattr(err, 'errno', None) == errno.ENOENT and
                                  stage not in self._pinned_scripts)
                errorCode = not_found if missing_script else permission_error
                self.logger.log(
                    'Plugin {0}: {1}-script validation failed; code={2}: {3}'.format(
                        self.pluginName, stage, errorCode, err), True, 'Error')
                self.close()
                return errorCode,dobackup,self.fsFreeze_on, self.pollSleepTime

        return errorCode,dobackup,self.fsFreeze_on, self.pollSleepTime

    def pre_script(self, pluginIndex, preScriptCompleted, preScriptResult):

            # Generates a system call to run the prescript
            # -- pluginIndex is the index for the current plugin assigned by pluginHost
            # -- preScriptCompleted is a bool array, upon completion of script, true will be assigned at pluginIndex
            # -- preScriptResult is an array and it stores the result at pluginIndex


        result = ScriptRunnerResult()
        result.requiredNoOfRetries = self.preScriptNoOfRetries

        self._run_pinned_script(
            'pre', self.preScriptParams, result,
            preScriptCompleted, preScriptResult, pluginIndex)

    def post_script(self, pluginIndex, postScriptCompleted, postScriptResult):
        result = ScriptRunnerResult()
        result.requiredNoOfRetries = self.postScriptNoOfRetries
        self._run_pinned_script(
            'post', self.postScriptParams, result,
            postScriptCompleted, postScriptResult, pluginIndex)

    def _run_pinned_script(self, stage, params, result, completed, results, index):
        """Execute only a validated handle and always publish worker completion."""
        script = None
        process = None
        failure = (CommonVariables.FailedPrepostPreScriptFailed if stage == 'pre'
                   else CommonVariables.FailedPrepostPostScriptFailed)
        timeout = (CommonVariables.FailedPrepostPreScriptTimeout if stage == 'pre'
                   else CommonVariables.FailedPrepostPostScriptTimeout)
        try:
            with self._script_lock:
                pinned = self._pinned_scripts.get(stage)
                if pinned is None:
                    raise OSError(errno.EBADF, 'No validated script handle')
                # The worker owns a duplicate so host cleanup cannot reuse its fd
                # while a timed-out or delayed worker is still starting its shell.
                script = pinned.duplicate()
            paramsStr = ['/bin/sh', script.execution_path()]
            paramsStr.extend(str(param) for param in params)
            self.logger.log(
                'Running plugin {0} {1}-script from pinned device={2}, inode={3}'.format(
                    self.pluginName, stage, script.device, script.inode),
                True, 'Info')
            process = subprocess.Popen(paramsStr, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, close_fds=True)
            flag_timeout = False
            curr = 0
            cnt = 0
            while True:
                while process.poll() is None:
                    if curr >= self.pollTotalCount:
                        flag_timeout = True
                        break
                    curr = curr + 1
                    time.sleep(self.pollSleepTime)
                if process.returncode == CommonVariables.PrePost_ScriptStatus_Success:
                    break
                if flag_timeout or cnt >= result.requiredNoOfRetries:
                    break
                cnt = cnt + 1
            result.noOfRetries = cnt
            if flag_timeout:
                result.errorCode = timeout
                result.continueBackup = self.continueBackupOnFailure
                self.logger.log('Plugin {0} {1}-script timed out; code={2}'.format(
                    self.pluginName, stage, timeout), True, 'Error')
            elif process.returncode != CommonVariables.PrePost_ScriptStatus_Success:
                result.errorCode = failure
                result.continueBackup = self.continueBackupOnFailure
                self.logger.log(
                    'Plugin {0} {1}-script exited with status={2}; code={3}'.format(
                        self.pluginName, stage, process.returncode, failure),
                    True, 'Error')
            else:
                result.errorCode = CommonVariables.PrePost_ScriptStatus_Success
                if stage == 'pre':
                    self.PreScriptCompletedSuccessfully = True
                self.logger.log('Plugin {0} {1}-script completed successfully'.format(
                    self.pluginName, stage), True, 'Info')
        except (OSError, ValueError) as err:
            result.errorCode = failure
            result.continueBackup = self.continueBackupOnFailure
            self.logger.log(
                'Plugin {0} {1}-script execution failed; code={2}: {3}'.format(
                    self.pluginName, stage, failure, err), True, 'Error')
        finally:
            try:
                if process is not None:
                    try:
                        # Do not release a procfs handle while its shell may still
                        # need to open it. Bound that lifetime on timeout as well.
                        if process.poll() is None:
                            try:
                                process.kill()
                            except OSError as err:
                                if process.poll() is None:
                                    result.errorCode = failure
                                    result.continueBackup = self.continueBackupOnFailure
                                    self.logger.log(
                                        'Cannot stop plugin {0} {1}-script shell; '
                                        'retaining its descriptor until exit: {2}'.format(
                                            self.pluginName, stage, err),
                                        True, 'Error')
                        process.wait()
                    finally:
                        process.stdout.close()
                        process.stderr.close()
            except OSError as err:
                result.errorCode = failure
                result.continueBackup = self.continueBackupOnFailure
                self.logger.log(
                    'Plugin {0} {1}-script process cleanup failed: {2}'.format(
                        self.pluginName, stage, err), True, 'Error')
            finally:
                try:
                    if script is not None:
                        script.close()
                except OSError as err:
                    result.errorCode = failure
                    result.continueBackup = self.continueBackupOnFailure
                    self.logger.log(
                        'Plugin {0} {1}-script descriptor cleanup failed: {2}'.format(
                            self.pluginName, stage, err), True, 'Error')
                finally:
                    results[index] = result
                    completed[index] = True
