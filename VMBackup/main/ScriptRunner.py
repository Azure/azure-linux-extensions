import json
import subprocess
import time
import os
import errno
import fcntl
import threading
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
        self._script_fds = {}
        self._script_lock = threading.Lock()

    def close(self):
        """Close only handles not yet handed to an execution worker."""
        with self._script_lock:
            while self._script_fds:
                _, fd = self._script_fds.popitem()
                os.close(fd)

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
        except IOError:
            errMsg = 'Error in opening ' + self.pluginName + ' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        except ValueError as err:
            errMsg = 'Error in decoding ' + self.pluginName + ' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        except KeyError as err:
            errMsg = 'Error in fetching value for the key '+str(err) + ' in ' +self.pluginName+' config file.' + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')

    def find_owner(self, filename, fd=None):
        file_owner = ''
        try:
            metadata = os.stat(filename) if fd is None else os.fstat(fd)
            file_owner = getpwuid(metadata.st_uid).pw_name
        except Exception as err:
            errMsg = 'Error in fetching owner of the file : ' + filename  + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')

        return file_owner

    def validate_permissions(self, filename, fd=None):
        valid_permissions = True
        try:
            metadata = os.stat(filename) if fd is None else os.fstat(fd)
            permissions = oct(metadata[ST_MODE])[-3:]
            self.logger.log('Permissions of the file ' + filename + ' are ' + permissions,True)
            if int(permissions[1]) > 0 : #validating permissions for group
                valid_permissions = False
            if int(permissions[2]) > 0 : #validating permissions for others
                valid_permissions = False
        except Exception as err:
            errMsg = 'Error in fetching permissions of the file : ' + filename  + ': %s, stack trace: %s' % (str(err), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            valid_permissions = False

        return valid_permissions

    def _open_validated_script(self, path, not_found, permission_error):
        """On success the caller owns the fd; failures close it here."""
        fd = None
        retained = False
        errorCode = permission_error
        try:
            # Validate the opened target, including supported symlinks. Nonblocking
            # open avoids hanging if the configured name was replaced with a FIFO.
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_CLOEXEC', 0))
            fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            metadata = os.fstat(fd)
            if not S_ISREG(metadata.st_mode):
                errorCode = not_found
            elif self.validate_permissions(path, fd) and self.find_owner(path, fd) == 'root':
                self._script_path(fd)
                self.logger.log(
                    'Validated script {0}: fd={1}, device={2}, inode={3}'.format(
                        path, fd, metadata.st_dev, metadata.st_ino), True, 'Info')
                retained = True
                return fd, CommonVariables.PrePost_PluginStatus_Success
            self.logger.log('Script validation rejected {0}: uid={1}, mode={2}; code={3}'.format(
                path, metadata.st_uid, oct(metadata.st_mode & 0o777), errorCode), True, 'Error')
        except (OSError, AttributeError) as err:
            if fd is None and getattr(err, 'errno', None) in (
                    errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                errorCode = not_found
            self.logger.log('Cannot validate script {0}; code={1}: {2}'.format(
                path, errorCode, err), True, 'Error')
        finally:
            if fd is not None and not retained:
                os.close(fd)
        return None, errorCode

    def _script_path(self, fd):
        # Use the parent's descriptor so Python 2.7 needs neither descriptor
        # inheritance nor preexec_fn in the threaded plugin host.
        path = '/proc/{0}/fd/{1}'.format(os.getpid(), fd)
        opened, referenced = os.fstat(fd), os.stat(path)
        if (opened.st_dev, opened.st_ino) != (referenced.st_dev, referenced.st_ino):
            raise OSError(errno.EACCES, 'Script procfs identity mismatch')
        return path

    def _take_script(self, stage):
        # Handover and host cleanup share a lock. Once removed, only this worker
        # (or its timeout cleanup waiter) is allowed to close the same handle.
        with self._script_lock:
            fd = self._script_fds.pop(stage, None)
        if fd is None:
            raise OSError(errno.EBADF, 'No validated ' + stage + '-script handle')
        try:
            return fd, self._script_path(fd)
        except (OSError, AttributeError):
            os.close(fd)
            raise

    def validate_scripts(self):

        errorCode = CommonVariables.PrePost_PluginStatus_Success
        dobackup = True

        self.close()
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

        for stage, path, not_found, permission_error in [
                ('pre', self.preScriptLocation, CommonVariables.FailedPrepostPreScriptNotFound,
                 CommonVariables.FailedPrepostPreScriptPermissionError),
                ('post', self.postScriptLocation, CommonVariables.FailedPrepostPostScriptNotFound,
                 CommonVariables.FailedPrepostPostScriptPermissionError)]:
            fd, errorCode = self._open_validated_script(path, not_found, permission_error)
            if errorCode != CommonVariables.PrePost_PluginStatus_Success:
                self.close()
                return errorCode,dobackup,self.fsFreeze_on, self.pollSleepTime
            self._script_fds[stage] = fd

        return errorCode,dobackup,self.fsFreeze_on, self.pollSleepTime

    def pre_script(self, pluginIndex, preScriptCompleted, preScriptResult):

            # Generates a system call to run the prescript
            # -- pluginIndex is the index for the current plugin assigned by pluginHost
            # -- preScriptCompleted is a bool array, upon completion of script, true will be assigned at pluginIndex
            # -- preScriptResult is an array and it stores the result at pluginIndex


        result = ScriptRunnerResult()
        result.requiredNoOfRetries = self.preScriptNoOfRetries
        try:
            fd, scriptPath = self._take_script('pre')
        except (OSError, AttributeError) as err:
            self.logger.log('Cannot execute validated prescript for ' + self.pluginName + ': ' + str(err), True, 'Error')
            result.errorCode = CommonVariables.FailedPrepostPreScriptFailed
            result.continueBackup = self.continueBackupOnFailure
            preScriptResult[pluginIndex] = result
            preScriptCompleted[pluginIndex] = True
            return

        process = None
        try:
            paramsStr = ['sh',scriptPath]
            for param in self.preScriptParams:
                paramsStr.append(str(param))

            self.logger.log('Running prescript for '+self.pluginName+' module...',True,'Info')
            process = subprocess.Popen(paramsStr, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)

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
                if result.errorCode != CommonVariables.PrePost_ScriptStatus_Success:
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
        finally:
            self._release_script(fd, process)

    def post_script(self, pluginIndex, postScriptCompleted, postScriptResult):

            # Generates a system call to run the postscript
            # -- pluginIndex is the index for the current plugin assigned by pluginHost
            # -- postScriptCompleted is a bool array, upon completion of script, true will be assigned at pluginIndex
            # -- postScriptResult is an array and it stores the result at pluginIndex

        result = ScriptRunnerResult()

        result.requiredNoOfRetries = self.postScriptNoOfRetries
        try:
            fd, scriptPath = self._take_script('post')
        except (OSError, AttributeError) as err:
            self.logger.log('Cannot execute validated postscript for ' + self.pluginName + ': ' + str(err), True, 'Error')
            result.errorCode = CommonVariables.FailedPrepostPostScriptFailed
            result.continueBackup = self.continueBackupOnFailure
            postScriptResult[pluginIndex] = result
            postScriptCompleted[pluginIndex] = True
            return

        process = None
        try:
            paramsStr = ['sh',scriptPath]
            for param in self.postScriptParams:
                paramsStr.append(str(param))

            self.logger.log('Running postscript for '+self.pluginName+' module...',True,'Info')
            process = subprocess.Popen(paramsStr, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)

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
                if result.errorCode != CommonVariables.PrePost_ScriptStatus_Success:
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
        finally:
            self._release_script(fd, process)

    def _release_script(self, fd, process):
        """Take ownership from the worker, deferring close if its shell is live."""
        if process is not None and process.poll() is None:
            # Preserve the timeout result without killing or waiting for the
            # shell. Its existing handle is handed to this cleanup waiter.
            cleanup = threading.Thread(target=self._wait_and_close_script, args=(fd, process))
            cleanup.daemon = True
            try:
                cleanup.start()
            except RuntimeError as err:
                self.logger.log('Cannot start script cleanup for ' + self.pluginName + '; waiting for shell exit: ' + str(err), True, 'Error')
                self._wait_and_close_script(fd, process)
            return cleanup
        self._wait_and_close_script(fd, process)

    def _wait_and_close_script(self, fd, process):
        if process is not None:
            try:
                process.wait()
            except OSError as err:
                self.logger.log('Script cleanup wait failed for ' + self.pluginName + ': ' + str(err), True, 'Error')
                if process.poll() is None:
                    self.logger.log('Shell exit unconfirmed; retaining script handle until extension exit', True, 'Error')
                    return
        try:
            if process is not None:
                process.stdout.close()
                process.stderr.close()
        finally:
            os.close(fd)
