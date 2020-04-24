import subprocess
import os
import tempfile
import traceback
import time
import sys
import pwd
import base64
import Utils.constants as constants
import xml.sax.saxutils as xml_utils
import Utils.logger

global logger
# overwrite the logger in the tests
logger = Utils.logger.default_logger


def change_owner(file_path, user):
    """
    Lookup user.  Attempt chown 'filepath' to 'user'.
    """
    p = None
    try:
        p = pwd.getpwnam(user)
    except KeyError:
        pass
    except OSError:
        pass
    if p is not None:
        os.chown(file_path, uid=p[2], gid=p[3])


def create_dir(dir_path, user, mode):
    """
    Attempt os.makedirs, catch all exceptions.
    Call ChangeOwner afterwards.
    """
    try:
        os.makedirs(dir_path, mode)
    except OSError:
        pass
    change_owner(dir_path, user)


def set_file_contents(file_path, contents):
    """
    Write 'contents' to 'file_path'.
    """
    if type(contents) == str:
        contents = contents.encode('latin-1', 'ignore')
    try:
        with open(file_path, "wb+") as F:
            F.write(contents)
    except OSError as e:
        logger.error_with_prefix('SetFileContents', 'Writing to file ' + file_path + ' Exception is ' + str(e))
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
    except OSError as e:
        logger.error_with_prefix('AppendFileContents', 'Appending to file ' + file_path + ' Exception is ' + str(e))
        return None
    return 0


def get_file_contents(file_path, as_bin=False):
    """
    Read and return contents of 'file_path'.
    """
    mode = 'r'
    if as_bin:
        mode += 'b'
    try:
        with open(file_path, mode) as F:
            contents = F.read()
            return contents
    except OSError as e:
        logger.error_with_prefix('GetFileContents', 'Reading from file ' + file_path + ' Exception is ' + str(e))
        return None


def replace_file_with_contents_atomic(filepath, contents):
    """
    Write 'contents' to 'filepath' by creating a temp file, and replacing original.
    """
    handle, temp = tempfile.mkstemp(dir=os.path.dirname(filepath))
    if type(contents) == str:
        contents = contents.encode('latin-1')
    try:
        os.write(handle, contents)
    except OSError as e:
        logger.error_with_prefix('ReplaceFileContentsAtomic', 'Writing to file ' + filepath + ' Exception is ' + str(e))
        return None
    finally:
        os.close(handle)
    try:
        os.rename(temp, filepath)
        return None
    except OSError as e:
        logger.error_with_prefix(
            'ReplaceFileContentsAtomic', 'Renaming ' + temp + ' to ' + filepath + ' Exception is ' + str(e)
        )
    try:
        os.remove(filepath)
    except OSError as e:
        logger.error_with_prefix('ReplaceFileContentsAtomic', 'Removing ' + filepath + ' Exception is ' + str(e))
    try:
        os.rename(temp, filepath)
    except OSError as e:
        logger.error_with_prefix('ReplaceFileContentsAtomic', 'Removing ' + filepath + ' Exception is ' + str(e))
        return 1
    return 0


def run_command_and_write_stdout_to_file(command, output_file):
    # meant to replace commands of the nature command > output_file
    try:
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        stdout, stderr = p.communicate()
    except OSError as e:
        logger.error('CalledProcessError.  Error message is ' + str(e))
        return e.errno
    if p.returncode != 0:
        logger.error('CalledProcessError.  Error Code is ' + str(p.returncode))
        logger.error('CalledProcessError.  Command string was ' + ' '.join(command))
        logger.error('CalledProcessError.  Command result was stdout: ' + str(stdout) + ' stderr: ' + str(stderr))
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
        logger.log_if_verbose(cmd)
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=False)
    except subprocess.CalledProcessError as e:
        if chk_err and log_cmd:
            logger.error('CalledProcessError.  Error Code is ' + str(e.returncode))
            logger.error('CalledProcessError.  Command string was ' + e.cmd)
            logger.error('CalledProcessError.  Command result was ' + (e.output[:-1]).decode('latin-1'))
        return e.returncode, e.output.decode('latin-1')
    except OSError as e:
        if chk_err and log_cmd:
            logger.error('CalledProcessError.  Error message is ' + str(e))
            return e.errno, str(e)
    # noinspection PyUnboundLocalVariable
    return 0, output.decode('latin-1')


def run(cmd, chk_err=True):
    """
    Calls RunGetOutput on 'cmd', returning only the return code.
    If chk_err=True then errors will be reported in the log.
    If chk_err=False then errors will be suppressed from the log.
    """
    return_code, _ = run_command_get_output(cmd, chk_err)
    return return_code


# noinspection PyUnboundLocalVariable
def run_send_stdin(cmd, cmd_input, chk_err=True, log_cmd=True):
    """
    Wrapper for subprocess.Popen.
    Execute 'cmd', sending 'input' to STDIN of 'cmd'.
    Returns return code and STDOUT, trapping expected exceptions.
    Reports exceptions to Error if chk_err parameter is True
    """
    if log_cmd:
        logger.log_if_verbose(str(cmd) + cmd_input)
    subprocess_executed = False
    try:
        me = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        output = me.communicate(cmd_input)
        subprocess_executed = True
    except OSError as e:
        if chk_err and log_cmd:
            logger.error('CalledProcessError.  Error Code is ' + str(e.errno))
            logger.error('CalledProcessError.  Command string was ' + cmd)
            logger.error('CalledProcessError.  Command result was ' + str(e))
            return 1, str(e)
    if subprocess_executed and me.returncode != 0 and chk_err and log_cmd:
        logger.error('CalledProcessError.  Error Code is ' + str(me.returncode))
        logger.error('CalledProcessError.  Command string was ' + cmd)
        logger.error('CalledProcessError.  Command result was ' + output[0].decode('latin-1'))
    return me.returncode, output[0].decode('latin-1')


def get_line_starting_with(prefix, filepath):
    """
    Return line from 'filepath' if the line startswith 'prefix'
    """
    for line in get_file_contents(filepath).split('\n'):
        if line.startswith(prefix):
            return line
    return None


def translate_custom_data(data, configuration):
    """
    Translate the custom data from a Base64 encoding. Default to no-op.
    """
    data_to_decode = configuration.get("Provisioning.DecodeCustomData")
    if data_to_decode is not None and data_to_decode.lower().startswith("y"):
        return base64.b64decode(data)
    return data


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
        str_event_id = u'<Event id="{0}"/>'.format(self.eventId)
        str_provider_id = u'<Provider id="{0}"/>'.format(self.providerId)
        str_record_format = u'<Param Name="{0}" Value="{1}" T="{2}" />'
        str_record_no_quote_format = u'<Param Name="{0}" Value={1} T="{2}" />'
        str_mt_str = u'mt:wstr'
        str_mt_u_int64 = u'mt:uint64'
        str_mt_bool = u'mt:bool'
        str_mt_float = u'mt:float64'
        str_events_data = u""

        for attName in self.__dict__:
            if attName in ["eventId", "filedCount", "providerId"]:
                continue

            att_value = self.__dict__[attName]
            if type(att_value) is int:
                str_events_data += str_record_format.format(attName, att_value, str_mt_u_int64)
                continue
            if type(att_value) is str:
                att_value = xml_utils.quoteattr(att_value)
                str_events_data += str_record_no_quote_format.format(attName, att_value, str_mt_str)
                continue
            if str(type(att_value)).count("'unicode'") > 0:
                att_value = xml_utils.quoteattr(att_value)
                str_events_data += str_record_no_quote_format.format(attName, att_value, str_mt_str)
                continue
            if type(att_value) is bool:
                str_events_data += str_record_format.format(attName, att_value, str_mt_bool)
                continue
            if type(att_value) is float:
                str_events_data += str_record_format.format(attName, att_value, str_mt_float)
                continue

            logger.log("Warning: property " + attName + ":" + str(type(att_value)) + ":type" + str(
                type(att_value)) + "Can't convert to events data:" + ":type not supported")

        return u"<Data>{0}{1}{2}</Data>".format(str_provider_id, str_event_id, str_events_data)

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

    def __init__(self, wala_config_file):
        self.values = dict()
        if wala_config_file is None:
            wala_config_file = constants.waagent_config_path
        if not os.path.isfile(wala_config_file):
            raise ValueError("Missing configuration in {0}".format(wala_config_file))
        try:
            for line in get_file_contents(wala_config_file).split('\n'):
                if not line.startswith("#") and "=" in line:
                    parts = line.split()[0].split('=')
                    value = parts[1].strip("\" ")
                    if value != "None":
                        self.values[parts[0]] = value
                    else:
                        self.values[parts[0]] = None
        # when get_file_contents returns none
        except AttributeError:
            logger.error("Unable to parse {0}".format(wala_config_file))
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


def add_extension_event(name, op, is_success, duration=0, version="1.0", message="", extension_type="",
                        is_internal=False):
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
    except OSError:
        logger.error("Error " + traceback.format_exc())
