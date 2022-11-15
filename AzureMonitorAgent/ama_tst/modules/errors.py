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
warnings = set([WARN_INTERNET_CONN, WARN_INTERNET, WARN_OPENSSL_PROXY])

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
    ERR_GETTING_AMA_VER : "Couldn't get most current released version of AMA.\n\nError Details: \n{0}",
    
    ERR_AMA_PARAMETERS : "Couldn't read and parse AMA configuration in /etc/default/azuremonitoragent.\n\nError Details:\n{0}",
    ERR_NO_DCR : "Couldn't parse DCR information on this VM. Please check your DCR configuration.\n\nError Details:{0}",
    ERR_INFO_MISSING: "NO DCR workspace id or region is found. Please check if DCR is configured correctly and match the information in"\
            "/etc/opt/microsoft/azuremonitoragent/config-cache/configchunks.*.json",
    ERR_ENDPT : "Machine couldn't connect to {0}: curl/openssl command failed. "\
          "\n\nError Details:\n $ {1} \n\n{2}",
    ERR_SUBCOMPONENT_STATUS : "Subcomponent {0} has not been started. Status details: {1}",
    ERR_CHECK_STATUS : "Couldn't get the status of subcomponents.\n\nError Details:{0}",
    ERR_RESOLVE_IP : "The endpoint {0} cannot be resolved. Please run the command below for more information on the failure:\n\n $ {1}",
    ERR_IMDS_METADATA : "Couldn't access {0} Instance Metadata Service when executing command\n $ {1}\n\nError Details:\n{2}",
    ERR_ACCESS_TOKEN : "Couldn't use managed identities to acquire an access token when executing command\n $ {0}\n\nError Details:\n{1}",
    ERR_ENDPT_PROXY : "Machine couldn't connect to {0} with proxy: curl/openssl command failed. Please check your proxy configuration."\
          "\n\nError Details:\n $ {1} \n\n{2}",
    WARN_OPENSSL_PROXY : "Skip SSL handshake checks because AMA is configured with authenticated proxy."
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