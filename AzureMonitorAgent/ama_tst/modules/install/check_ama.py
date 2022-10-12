import re
import requests
import xml.dom.minidom

from error_codes import *
from errors      import error_info, get_input
from helpers     import get_package_version

AMA_URL = 'https://docs.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-extension-versions'

def get_latest_ama_version(curr_version):
    try:           
        r = requests.get(AMA_URL)
        tbody = r.text.split("<tbody>")[1].split("</tbody>")[0]
        tbody = "<tbody>" + tbody + "</tbody>"
        with xml.dom.minidom.parseString(tbody) as dom:
            rows = dom.getElementsByTagName("tr")
            for row in rows:
                cell = row.getElementsByTagName("td")[3]
                version = cell.firstChild.nodeValue
                version = re.sub('[A-Za-z ]+', '', version)
                if (version == ''):
                    continue
                if (comp_versions_ge(curr_version, version)):
                    return (None, None)
                else:
                    return (version, None)
    except Exception as e:
        return (None, e)
    return (None, None)

# compare two versions, see if the first is newer than / the same as the second
def comp_versions_ge(version1, version2):
        versions1 = [int(v) for v in version1.split(".")]
        versions2 = [int(v) for v in version2.split(".")]
        for i in range(max(len(versions1), len(versions2))):
            v1 = versions1[i] if i < len(versions1) else 0
            v2 = versions2[i] if i < len(versions2) else 0
            if v1 > v2:
                return True
            elif v1 < v2:
                return False
        return True

def ask_update_old_version(ama_version, curr_ama_version):
    print("--------------------------------------------------------------------------------")
    print("You are currently running AMA Verion {0}. There is a newer version\n"\
          "available which may fix your issue (version {1}).".format(ama_version, curr_ama_version))
    answer = get_input("Do you want to update? (y/n)", (lambda x : x.lower() in ['y','yes','n','no']),\
                       "Please type either 'y'/'yes' or 'n'/'no' to proceed.")
    # user does want to update
    if (answer.lower() in ['y', 'yes']):
        print("--------------------------------------------------------------------------------")
        print("Please follow the instructions given here:")
        print("\n    https://docs.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-manage\n")
        return USER_EXIT
    # user doesn't want to update
    elif (answer.lower() in ['n', 'no']):
        print("Continuing on with troubleshooter...")
        print("--------------------------------------------------------------------------------")
        return NO_ERROR

def check_ama(interactive):
    (ama_version, e) = get_package_version('azuremonitoragent')
    if (not e == None):
        error_info.append((e,))
        return ERR_AMA_INSTALL

    ama_version = ama_version.split('-')[0]
    if (not comp_versions_ge(ama_version, '1.21.0')):
        error_info.append((ama_version,))
        return ERR_OLD_AMA_VER

    (newer_ama_version, e) = get_latest_ama_version(ama_version)
    if (newer_ama_version == None):
        if (e == None):
            return NO_ERROR
        else:
            error_info.append((e,))
            return ERR_GETTING_AMA_VER
        
    else:
        # if not most recent version, ask if want to update
        if (interactive):
            if (ask_update_old_version(ama_version, newer_ama_version) == USER_EXIT):
                return USER_EXIT

    return NO_ERROR