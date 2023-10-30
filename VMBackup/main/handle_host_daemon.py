#!/usr/bin/env python

import time
import os
import sys
import json
import xml.etree.ElementTree as ET
from Utils.WAAgentUtil import waagent
from Utils import HandlerUtil
import datetime
from common import CommonVariables
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers

SCRIPT_DIR=os.path.dirname(os.path.realpath(__file__))


class HandlerContext:
    def __init__(self,name):
        self._name = name
        self._version = '0.0'
        return

class Handler:
    _log = None
    _error = None
    def __init__(self, log, error, short_name) -> None:
        self._context = HandlerContext(short_name)
        self._log = log
        self._error = error
        self.eventlogger = None
        self.log_message = ""
        handler_env_file = './HandlerEnvironment.json'
        if not os.path.isfile(handler_env_file):
            self.error("[handle_host_daemon.py] -> Unable to locate " + handler_env_file)
            return None
        ctxt = waagent.GetFileContents(handler_env_file)
        if ctxt == None :
            self.error("[handle_host_daemon] -> Unable to read " + handler_env_file)
        try:
            handler_env = json.loads(ctxt)
        except:
            pass
        if handler_env == None :
            self.log("JSON error processing " + handler_env_file)
            return None
        if type(handler_env) == list:
            handler_env = handler_env[0]
        self._context._name = handler_env['name']
        self._context._version = str(handler_env['version'])
        self._context._config_dir = handler_env['handlerEnvironment']['configFolder']
        self._context.log_dir = handler_env['handlerEnvironment']['logFolder']
        self._context.log_file = os.path.join(self._context.log_dir,'host_based_extension.log')
        self.logging_file=self._context.log_file

    def _get_log_prefix(self):
        return '[%s-%s]' % (self._context._name, self._context._version)

    def get_value_from_configfile(self, key):
        value = None
        configfile = '/etc/azure/vmbackup.conf'
        try :
            if os.path.exists(configfile):
                config = ConfigParsers.ConfigParser()
                config.read(configfile)
                if config.has_option('SnapshotThread',key):
                    value = config.get('SnapshotThread',key)
        except Exception as e:
            pass
        return value

    def get_strvalue_from_configfile(self, key, default):
        value = self.get_value_from_configfile(key)
        if value == None or value == '':
            value = default
        try :
            value_str = str(value)
        except ValueError :
            self.log('Not able to parse the read value as string, falling back to default value', 'Warning')
            value = default
        return value

    def get_intvalue_from_configfile(self, key, default):
        value = default
        value = self.get_value_from_configfile(key)
        if value == None or value == '':
            value = default
        try :
            value_int = int(value)
        except ValueError :
            self.log('Not able to parse the read value as int, falling back to default value', 'Warning')
            value = default

        return int(value)

    def log(self, message, level='Info'):
        # print("[Handler.log] -> Fired")
        try:
            self.log_with_no_try_except(message, level)
        except IOError:
            pass
        except Exception as e:
            try:
                errMsg = str(e) + 'Exception in hutil.log'
                self.log_with_no_try_except(errMsg, 'Warning')
            except Exception as e:
                pass

    def log_with_no_try_except(self, message, level='Info'):
        # print("[Handler.log_with_no_try_except] -> Fired")
        WriteLog = self.get_strvalue_from_configfile('WriteLog','True')
        if (WriteLog == None or WriteLog == 'True'):
            if sys.version_info > (3,):
                if self.logging_file is not None:
                    self.log_py3(message)
                    if self.eventlogger != None:
                        self.eventlogger.trace_message(level, message)
                else:
                    pass
            else:
                self._log(self._get_log_prefix() + message)
                if self.eventlogger != None:
                    self.eventlogger.trace_message(level, message)
            message = "{0}  {1}  {2} \n".format(str(datetime.datetime.utcnow()) , level , message)
        self.log_message = self.log_message + message

    def log_py3(self, msg):
        # print("[Handler.log_py3] -> Fired")
        if type(msg) is not str:
            msg = str(msg, errors="backslashreplace")
        msg = str(datetime.datetime.utcnow()) + " " + str(self._get_log_prefix()) + msg + "\n"
        try:
            with open(self.logging_file, "a+") as C :
                C.write(msg)
        except IOError:
            pass

    def error(self, message):
        self._error(self._get_log_prefix() + message)


def main():
    global SCRIPT_DIR
    HandlerUtil.waagent.LoggerInit('/dev/console','/dev/stdout')
    handler = Handler(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    starttime = time.monotonic()
    while True:
        handler.log("tick")
        print("tick")
        time.sleep(10.0 - ((time.monotonic() - starttime) % 10.0))

if __name__ == '__main__' :
    main()