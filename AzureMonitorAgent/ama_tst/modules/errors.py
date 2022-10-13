import copy
import subprocess

from error_codes import *

# backwards compatible input() function for Python 2 vs 3
try:
    input = raw_input
except NameError:
    pass

# error info edited when error occurs
error_info = []

# list of all errors called when script ran
err_summary = []



# # set of all errors which are actually warnings
warnings = set([WARN_INTERNET_CONN, WARN_INTERNET])

# dictionary correlating error codes to error messages
error_messages = {
    WARN_INTERNET : "SSL connection couldn't be verified. Please run the command below for more information on this warning:\n"\
          "\n  $ {0}\n",
    WARN_INTERNET_CONN : "Machine is not connected to the internet: openssl command failed. "\
          "Please run the command below for more information on the failure:\n"\
          "\n  $ {0}\n",
    ERR_SUDO_PERMS : "Couldn't access {0} due to inadequate permissions. Please run the troubleshooter "\
          "as root in order to allow access.",
    ERR_FOUND : "Please go through the output above to find the errors caught by the troubleshooter.",
    ERR_BITS : "Couldn't get AMA if CPU is not 64-bit.",
    ERR_OS_VER : "This version of {0} ({1}) is not supported. Please download {2}. To see all "\
          "supported Operating Systems, please go to:\n"\
          "\n   https://docs.microsoft.com/en-us/azure/azure-monitor/agents/agents-overview#linux\n",
    ERR_OS : "{0} is not a supported Operating System. To see all supported Operating "\
          "Systems, please go to:\n"\
          "\n   https://docs.microsoft.com/en-us/azure/azure-monitor/agents/agents-overview#linux\n",
    ERR_FINDING_OS : "Coudln't determine Operating System. To see all supported Operating "\
          "Systems, please go to:\n"\
          "\n   https://docs.microsoft.com/en-us/azure/azure-monitor/agents/agents-overview#linux\n" \
          "\n\nError Details: \n{0}",
    ERR_FREE_SPACE : "There isn't enough space in directory {0} to install AMA - there needs to be at least 500MB free, "\
          "but {0} has {1}MB free. Please free up some space and try installing again.",
    ERR_PKG_MANAGER : "This system does not have a supported package manager. Please install 'dpkg' or 'rpm' "\
          "and run this troubleshooter again.",
    ERR_MULTIPLE_AMA : "There is more than one instance of AMA installed, please remove the extra AMA packages.",
    ERR_AMA_INSTALL : "AMA package isn't installed correctly.\n\nError Details: \n{0}",
    ERR_SUBCOMPONENT_INSTALL : "Subcomponents(s) {0} not installed correctly.",
    ERR_LOG_DAEMON : "No logging daemon found. Please install rsyslog or syslog-ng.",
    ERR_SYSLOG_USER : "Syslog user is not created successfully.",
    ERR_OLD_AMA_VER : "You are currently running AMA Version {0}. This troubleshooter only "\
          "supports versions 1.9 and newer. Please upgrade to the newest version. You can find "\
          "more information at the link below:\n"\
          "\n    https://docs.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-manage\n",
    ERR_GETTING_AMA_VER : "Couldn't get most current released version of AMA.\n\nError Details: \n{0}"
}



# check if either has no error or is warning
def is_error(err_code):
    not_errs = warnings.copy()
    not_errs.add(NO_ERROR)
    return (err_code not in not_errs)



# for getting inputs from the user
def get_input(question, check_ans, no_fit):
    answer = input(" {0}: ".format(question))
    while (not check_ans(answer.lower())):
        print("Unclear input. {0}".format(no_fit))
        answer = input(" {0}: ".format(question))
    return answer

def print_errors(err_code):
    not_errors = set([NO_ERROR, USER_EXIT])
    if (err_code in not_errors):
        return err_code

    warning = False
    if (err_code in warnings):
        warning = True

    err_string = error_messages[err_code]
    # no formatting
    if (error_info == []):
        err_string = "ERROR FOUND: {0}".format(err_string)
        err_summary.append(err_string)
    # needs input
    else:
        while (len(error_info) > 0):
            tup = error_info.pop(0)
            temp_err_string = err_string.format(*tup)
            if (warning):
                final_err_string = "WARNING FOUND: {0}".format(temp_err_string)
            else:
                final_err_string = "ERROR FOUND: {0}".format(temp_err_string)
            err_summary.append(final_err_string)
    if (warning):
        print("WARNING(S) FOUND.")
        return NO_ERROR
    else:
        print("ERROR(S) FOUND.")
        return ERR_FOUND