import subprocess
import os
import tempfile
import traceback
import time
import sys
import pwd
import Utils.constants as constants
import xml.sax.saxutils as xml_utils
from Utils.logger import default_logger as logger


def change_owner(filepath, user):
    """
    Lookup user.  Attempt chown 'filepath' to 'user'.
    """
    p = None
    try:
        p = pwd.getpwnam(user)
    except:
        pass
    if p is not None:
        os.chown(filepath, p[2], p[3])


def create_dir(dirpath, user, mode):
    """
    Attempt os.makedirs, catch all exceptions.
    Call ChangeOwner afterwards.
    """
    try:
        os.makedirs(dirpath, mode)
    except:
        pass
    change_owner(dirpath, user)


def set_file_contents(file_path, contents):
    """
    Write 'contents' to 'file_path'.
    """
    if type(contents) == str:
        contents = contents.encode('latin-1', 'ignore')
    try:
        with open(file_path, "wb+") as F:
            F.write(contents)
    except IOError as e:
        logger.ErrorWithPrefix('SetFileContents', 'Writing to file ' + file_path + ' Exception is ' + str(e))
        return None
    return 0


def append_file_contents(file_path, contents):
    """
    Append 'contents' to 'file_path'.
    """
    if type(contents) == str:
        if sys.version_info[0] == 3:
            contents = contents.encode('latin-1').decode('latin-1')
        elif sys.version_info[0] == 2:
            contents = contents.encode('latin-1')
    try:
        with open(file_path, "a+") as F:
            F.write(contents)
    except IOError as e:
        logger.ErrorWithPrefix('AppendFileContents', 'Appending to file ' + file_path + ' Exception is ' + str(e))
        return None
    return 0


def get_file_contents(file_path, as_bin=False):
    """
    Read and return contents of 'file_path'.
    """
    mode = 'r'
    if as_bin:
        mode += 'b'
    c = None
    try:
        with open(file_path, mode) as F:
            c = F.read()
    except IOError as e:
        logger.ErrorWithPrefix('GetFileContents', 'Reading from file ' + file_path + ' Exception is ' + str(e))
        return None
    return c


def replace_file_with_contents_atomic(filepath, contents):
    """
    Write 'contents' to 'filepath' by creating a temp file, and replacing original.
    """
    handle, temp = tempfile.mkstemp(dir=os.path.dirname(filepath))
    if type(contents) == str:
        contents = contents.encode('latin-1')
    try:
        os.write(handle, contents)
    except IOError as e:
        logger.ErrorWithPrefix('ReplaceFileContentsAtomic', 'Writing to file ' + filepath + ' Exception is ' + str(e))
        return None
    finally:
        os.close(handle)
    try:
        os.rename(temp, filepath)
        return None
    except IOError as e:
        logger.ErrorWithPrefix('ReplaceFileContentsAtomic', 'Renaming ' + temp + ' to ' + filepath + ' Exception is ' + str(e))
    try:
        os.remove(filepath)
    except IOError as e:
        logger.ErrorWithPrefix('ReplaceFileContentsAtomic', 'Removing ' + filepath + ' Exception is ' + str(e))
    try:
        os.rename(temp, filepath)
    except IOError as e:
        logger.ErrorWithPrefix('ReplaceFileContentsAtomic', 'Removing ' + filepath + ' Exception is ' + str(e))
        return 1
    return 0


def run_command_and_write_stdout_to_file(command, output_file):
    # meant to replace commands of the nature command > output_file
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE);
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        logger.Error('CalledProcessError.  Error Code is ' + str(p.returncode))
        logger.Error('CalledProcessError.  Command string was ' + ' '.join(command))
        logger.Error('CalledProcessError.  Command result was stdout: ' + stdout + ' stderr: ' + stderr )
        return p.returncode
    set_file_contents(output_file, stdout)
    return 0


def run_command_get_output(cmd, chk_err=True, log_cmd=True):
    """
    Wrapper for subprocess.check_output.
    Execute 'cmd'.  Returns return code and STDOUT, trapping expected exceptions.
    Reports exceptions to Error if chk_err parameter is True
    """
    if log_cmd:
        logger.LogIfVerbose(cmd)
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=False)
    except subprocess.CalledProcessError as e:
        if chk_err and log_cmd:
            logger.Error('CalledProcessError.  Error Code is ' + str(e.returncode))
            logger.Error('CalledProcessError.  Command string was ' + e.cmd)
            logger.Error('CalledProcessError.  Command result was ' + (e.output[:-1]).decode('latin-1'))
        return e.returncode, e.output.decode('latin-1')
    return 0, output.decode('latin-1')


def run(cmd, chk_err=True):
    """
    Calls RunGetOutput on 'cmd', returning only the return code.
    If chk_err=True then errors will be reported in the log.
    If chk_err=False then errors will be suppressed from the log.
    """
    return_code, _ = run_command_get_output(cmd, chk_err)
    return return_code


def get_line_starting_with(prefix, filepath):
    """
    Return line from 'filepath' if the line startswith 'prefix'
    """
    for line in get_file_contents(filepath).split('\n'):
        if line.startswith(prefix):
            return line
    return None


class WALAEvent(object):
    def __init__(self):
        self.providerId = ""
        self.eventId = 1
        self.OpcodeName = ""
        self.KeywordName = ""
        self.TaskName = ""
        self.TenantName = ""
        self.RoleName = ""
        self.RoleInstanceName = ""
        self.ContainerId = ""
        self.ExecutionMode = "IAAS"
        self.OSVersion = ""
        self.GAVersion = ""
        self.RAM = 0
        self.Processors = 0

    def to_xml(self):
        strEventid = u'<Event id="{0}"/>'.format(self.eventId)
        strProviderid = u'<Provider id="{0}"/>'.format(self.providerId)
        strRecordFormat = u'<Param Name="{0}" Value="{1}" T="{2}" />'
        strRecordNoQuoteFormat = u'<Param Name="{0}" Value={1} T="{2}" />'
        strMtStr = u'mt:wstr'
        strMtUInt64 = u'mt:uint64'
        strMtBool = u'mt:bool'
        strMtFloat = u'mt:float64'
        strEventsData = u""

        for attName in self.__dict__:
            if attName in ["eventId", "filedCount", "providerId"]:
                continue

            attValue = self.__dict__[attName]
            if type(attValue) is int:
                strEventsData += strRecordFormat.format(attName, attValue, strMtUInt64)
                continue
            if type(attValue) is str:
                attValue = xml_utils.quoteattr(attValue)
                strEventsData += strRecordNoQuoteFormat.format(attName, attValue, strMtStr)
                continue
            if str(type(attValue)).count("'unicode'") > 0:
                attValue = xml_utils.quoteattr(attValue)
                strEventsData += strRecordNoQuoteFormat.format(attName, attValue, strMtStr)
                continue
            if type(attValue) is bool:
                strEventsData += strRecordFormat.format(attName, attValue, strMtBool)
                continue
            if type(attValue) is float:
                strEventsData += strRecordFormat.format(attName, attValue, strMtFloat)
                continue

            logger.Log("Warning: property " + attName + ":" + str(type(attValue)) + ":type" + str(
                type(attValue)) + "Can't convert to events data:" + ":type not supported")

        return u"<Data>{0}{1}{2}</Data>".format(strProviderid, strEventid, strEventsData)

    def save(self):
        event_folder = constants.LibDir + "/events"
        if not os.path.exists(event_folder):
            os.mkdir(event_folder)
            os.chmod(event_folder, 0o700)
        if len(os.listdir(event_folder)) > 1000:
            raise Exception("WriteToFolder:Too many file under " + event_folder + " exit")

        filename = os.path.join(event_folder, str(int(time.time() * 1000000)))
        with open(filename + ".tmp", 'wb+') as h_file:
            h_file.write(self.to_xml().encode("utf-8"))
        os.rename(filename + ".tmp", filename + ".tld")


class ExtensionEvent(WALAEvent):
    def __init__(self):
        WALAEvent.__init__(self)
        self.eventId = 1
        self.providerId = "69B669B9-4AF8-4C50-BDC4-6006FA76E975"
        self.Name = ""
        self.Version = ""
        self.IsInternal = False
        self.Operation = ""
        self.OperationSuccess = True
        self.ExtensionType = ""
        self.Message = ""
        self.Duration = 0


class ConfigurationProvider(object):
    """
    Parse amd store key:values in waagent.conf
    """

    def __init__(self, walaConfigFile):
        self.values = dict()
        if walaConfigFile is None:
            walaConfigFile = constants.waagent_config_path
        if not os.path.isfile(walaConfigFile):
            raise Exception("Missing configuration in {0}".format(walaConfigFile))
        try:
            for line in get_file_contents(walaConfigFile).split('\n'):
                if not line.startswith("#") and "=" in line:
                    parts = line.split()[0].split('=')
                    value = parts[1].strip("\" ")
                    if value != "None":
                        self.values[parts[0]] = value
                    else:
                        self.values[parts[0]] = None
        except:
            logger.Error("Unable to parse {0}".format(walaConfigFile))
            raise
        return

    def get(self, key):
        return self.values.get(key)

    def yes(self, key):
        config_value = self.get(key)
        if config_value is not None and config_value.lower().startswith("y"):
            return True
        else:
            return False

    def no(self, key):
        config_value = self.get(key)
        if config_value is not None and config_value.lower().startswith("n"):
            return True
        else:
            return False


def add_extension_event(name, op, is_success, duration=0, version="1.0", message="", extension_type="", is_internal=False):
    event = ExtensionEvent()
    event.Name = name
    event.Version = version
    event.IsInternal = is_internal
    event.Operation = op
    event.OperationSuccess = is_success
    event.Message = message
    event.Duration = duration
    event.ExtensionType = extension_type
    try:
        event.save()
    except IOError:
        logger.Error("Error " + traceback.format_exc())

