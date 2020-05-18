import time
import sys
import string


# noinspection PyMethodMayBeStatic
class Logger(object):
    """
    The Agent's logging assumptions are:
    For Log, and LogWithPrefix all messages are logged to the
    self.file_path and to the self.con_path.  Setting either path
    parameter to None skips that log.  If Verbose is enabled, messages
    calling the LogIfVerbose method will be logged to file_path yet
    not to con_path.  Error and Warn messages are normal log messages
    with the 'ERROR:' or 'WARNING:' prefix added.
    """

    def __init__(self, filepath, conpath, verbose=False):
        """
        Construct an instance of Logger.
        """
        self.file_path = filepath
        self.con_path = conpath
        self.verbose = verbose

    def throttle_log(self, counter):
        """
        Log everything up to 10, every 10 up to 100, then every 100.
        """
        return (counter < 10) or ((counter < 100) and ((counter % 10) == 0)) or ((counter % 100) == 0)

    def write_to_file(self, message):
        """
        Write 'message' to logfile.
        """
        if self.file_path:
            try:
                with open(self.file_path, "a") as F:
                    message = filter(lambda x: x in string.printable, message)

                    # encoding works different for between interpreter version, we are keeping separate implementation
                    # to ensure backward compatibility
                    if sys.version_info[0] == 3:
                        message = ''.join(list(message)).encode('ascii', 'ignore').decode("ascii", "ignore")
                    elif sys.version_info[0] == 2:
                        message = message.encode('ascii', 'ignore')

                    F.write(message + "\n")
            except IOError as e:
                pass

    def write_to_console(self, message):
        """
        Write 'message' to /dev/console.
        This supports serial port logging if the /dev/console
        is redirected to ttys0 in kernel boot options.
        """
        if self.con_path:
            try:
                with open(self.con_path, "w") as C:
                    message = filter(lambda x: x in string.printable, message)

                    # encoding works different for between interpreter version, we are keeping separate implementation
                    # to ensure backward compatibility
                    if sys.version_info[0] == 3:
                        message = ''.join(list(message)).encode('ascii', 'ignore').decode("ascii", "ignore")
                    elif sys.version_info[0] == 2:
                        message = message.encode('ascii', 'ignore')

                    C.write(message + "\n")
            except IOError as e:
                pass

    def log(self, message):
        """
        Standard Log function.
        Logs to self.file_path, and con_path
        """
        self.log_with_prefix("", message)

    def log_to_console(self, message):
        """
        Logs message to console by pre-pending each line of 'message' with current time.
        """
        log_prefix = self._get_log_prefix("")
        for line in message.split('\n'):
            line = log_prefix + line
            self.write_to_console(line)

    def log_to_file(self, message):
        """
        Logs message to file by pre-pending each line of 'message' with current time.
        """
        log_prefix = self._get_log_prefix("")
        for line in message.split('\n'):
            line = log_prefix + line
            self.write_to_file(line)

    def no_log(self, message):
        """
        Don't Log.
        """
        pass

    def log_if_verbose(self, message):
        """
        Only log 'message' if global Verbose is True.
        """
        self.log_with_prefix_if_verbose('', message)

    def log_with_prefix(self, prefix, message):
        """
        Prefix each line of 'message' with current time+'prefix'.
        """
        log_prefix = self._get_log_prefix(prefix)
        for line in message.split('\n'):
            line = log_prefix + line
            self.write_to_file(line)
            self.write_to_console(line)

    def log_with_prefix_if_verbose(self, prefix, message):
        """
        Only log 'message' if global Verbose is True.
        Prefix each line of 'message' with current time+'prefix'.
        """
        if self.verbose:
            log_prefix = self._get_log_prefix(prefix)
            for line in message.split('\n'):
                line = log_prefix + line
                self.write_to_file(line)
                self.write_to_console(line)

    def warning(self, message):
        self.log_with_prefix("WARNING:", message)

    def error_with_prefix(self, prefix, message):
        self.log_with_prefix("ERROR: " + str(prefix), message)

    def error(self, message):
        """
        Call ErrorWithPrefix(message).
        """
        self.error_with_prefix("", message)

    def _get_log_prefix(self, prefix):
        """
        Generates the log prefix with timestamp+'prefix'.
        """
        t = time.localtime()
        t = "%04u/%02u/%02u %02u:%02u:%02u " % (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
        return t + prefix

# meant to be used with tests
# noinspection PyMethodMayBeStatic
class TestLogger(Logger):
    def __init__(self):
        super(Logger, self).__init__()
        self.verbose = True
        self.con_path = None
        self.file_path = None

    def _log_to_stdout(self, message):
        sys.stdout.writelines(message)
        sys.stdout.write("\n")

    def write_to_file(self, message):
        self._log_to_stdout(message)

    def write_to_console(self, message):
        self._log_to_stdout(message)

    def log(self, message):
        self._log_to_stdout(message)

    def log_to_console(self, message):
        self._log_to_stdout(message)

    def log_to_file(self, message):
        self._log_to_stdout(message)

    def log_if_verbose(self, message):
        self._log_to_stdout(message)

    def log_with_prefix(self, prefix, message):
        log_prefix = self._get_log_prefix(prefix)
        for line in message.split('\n'):
            line = log_prefix + line
            self._log_to_stdout(line)

    def log_with_prefix_if_verbose(self, prefix, message):
        self.log_with_prefix(prefix, message)

    def warning(self, message):
        self.log_with_prefix("WARNING:", message)

    def error_with_prefix(self, prefix, message):
        self.log_with_prefix("ERROR:", message)

    def error(self, message):
        self.error_with_prefix("", message)


global global_shared_context_logger
try:
    # test whether global_shared_context_logger has been assigned previously
    _ = global_shared_context_logger
except NameError:
    # previously not assigned, assign default value
    # will assign global_shared_context_logger only once
    global_shared_context_logger = Logger('/var/log/waagent.log', '/dev/console')


def log(message):
    global_shared_context_logger.log(message)


def error(message):
    global_shared_context_logger.error(message)


def warning(message):
    global_shared_context_logger.warning(message)


def error_with_prefix(prefix, message):
    global_shared_context_logger.error_with_prefix(prefix, message)


def log_if_verbose(message):
    global_shared_context_logger.log_if_verbose(message)
