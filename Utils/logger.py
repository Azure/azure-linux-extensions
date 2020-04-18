import time
import sys
import string


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

    def ThrottleLog(self, counter):
        """
        Log everything up to 10, every 10 up to 100, then every 100.
        """
        return (counter < 10) or ((counter < 100) and ((counter % 10) == 0)) or ((counter % 100) == 0)

    def WriteToFile(self, message):
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

    def WriteToConsole(self, message):
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

    def Log(self, message):
        """
        Standard Log function.
        Logs to self.file_path, and con_path
        """
        self.LogWithPrefix("", message)

    def LogToConsole(self, message):
        """
        Logs message to console by pre-pending each line of 'message' with current time.
        """
        log_prefix = self._get_log_prefix("")
        for line in message.split('\n'):
            line = log_prefix + line
            self.WriteToConsole(line)

    def LogToFile(self, message):
        """
        Logs message to file by pre-pending each line of 'message' with current time.
        """
        log_prefix = self._get_log_prefix("")
        for line in message.split('\n'):
            line = log_prefix + line
            self.WriteToFile(line)

    def NoLog(self, message):
        """
        Don't Log.
        """
        pass

    def LogIfVerbose(self, message):
        """
        Only log 'message' if global Verbose is True.
        """
        self.LogWithPrefixIfVerbose('', message)

    def LogWithPrefix(self, prefix, message):
        """
        Prefix each line of 'message' with current time+'prefix'.
        """
        log_prefix = self._get_log_prefix(prefix)
        for line in message.split('\n'):
            line = log_prefix + line
            self.WriteToFile(line)
            self.WriteToConsole(line)

    def LogWithPrefixIfVerbose(self, prefix, message):
        """
        Only log 'message' if global Verbose is True.
        Prefix each line of 'message' with current time+'prefix'.
        """
        if self.verbose == True:
            log_prefix = self._get_log_prefix(prefix)
            for line in message.split('\n'):
                line = log_prefix + line
                self.WriteToFile(line)
                self.WriteToConsole(line)

    def Warn(self, message):
        """
        Prepend the text "WARNING:" for each line in 'message'.
        """
        self.LogWithPrefix("WARNING:", message)

    def ErrorWithPrefix(self, prefix, message):
        """
        Prepend the text "ERROR:" to the prefix for each line in 'message'.
        Errors written to logfile, and /dev/console
        """
        self.LogWithPrefix("ERROR:", message)

    def Error(self, message):
        """
        Call ErrorWithPrefix(message).
        """
        self.ErrorWithPrefix("", message)

    def _get_log_prefix(self, prefix):
        """
        Generates the log prefix with timestamp+'prefix'.
        """
        t = time.localtime()
        t = "%04u/%02u/%02u %02u:%02u:%02u " % (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
        return t + prefix


global default_logger
default_logger = Logger('/var/log/waagent.log', '/dev/console')