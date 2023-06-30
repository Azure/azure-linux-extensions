import os
import json
import platform
import subprocess
from errors         import error_info
from error_codes    import *

CONFIG_DIR = '/etc/opt/microsoft/azuremonitoragent/config-cache/configchunks'
METRICS_FILE = "/etc/opt/microsoft/azuremonitoragent/config-cache/metricCounters.json"

# backwards compatible input() function for Python 2 vs 3
try:
    input = raw_input
except NameError:
    pass

# backwards compatible devnull variable for Python 3.3 vs earlier
try:
    DEVNULL = subprocess.DEVNULL
except:
    DEVNULL = open(os.devnull)

general_info = dict()

def geninfo_lookup(key):
    try:
        val = general_info[key]
    except KeyError:
        return None
    return val

def get_input(question, check_ans=None, no_fit=None):
    if check_ans == None and no_fit == None:
        return input(question)
    answer = input(" {0}: ".format(question))
    while (not check_ans(answer.lower())):
        print("Unclear input. {0}".format(no_fit))
        answer = input(" {0}: ".format(question))
    return answer

def is_arc_installed():
    """
    Check if this is an Arc machine
    """
    # Using systemctl to check this since Arc only supports VMs that have systemd
    check_arc = os.system('systemctl status himdsd 1>/dev/null 2>&1')
    return check_arc == 0

def find_vm_bits():
    cpu_info = subprocess.check_output(['lscpu'], universal_newlines=True)
    cpu_opmodes = (cpu_info.split('\n'))[1]
    cpu_bits = cpu_opmodes[-6:]
    return cpu_bits

def find_vm_distro():
    """
    Finds the Linux Distribution this vm is running on.
    """
    vm_dist = vm_id = vm_ver =  None
    parse_manually = False
    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        try:
            vm_dist, vm_ver, vm_id = platform.dist()
        except AttributeError:
            # Falling back to /etc/os-release distribution parsing
            pass

    # Some python versions *IF BUILT LOCALLY* (ex 3.5) give string responses (ex. 'bullseye/sid') to platform.dist() function
    # This causes exception in the method below. Thus adding a check to switch to manual parsing in this case
    try:
        temp_vm_ver = int(vm_ver.split('.')[0])
    except:
        parse_manually = True

    if (not vm_dist and not vm_ver) or parse_manually: # SLES 15 and others
        try:
            with open('/etc/os-release', 'r') as fp:
                for line in fp:
                    if line.startswith('ID='):
                        vm_dist = line.split('=')[1]
                        vm_dist = vm_dist.split('-')[0]
                        vm_dist = vm_dist.replace('\"', '').replace('\n', '')
                        vm_dist = vm_dist.lower()
                    elif line.startswith('VERSION_ID='):
                        vm_ver = line.split('=')[1]
                        vm_ver = vm_ver.replace('\"', '').replace('\n', '')
                        vm_ver = vm_ver.lower()
        except (FileNotFoundError, AttributeError) as e:  # indeterminate OS
            return (None, None, e)
    return (vm_dist, vm_ver, None)


def find_package_manager():
    global general_info
    """
    Checks which package manager is on the system
    """
    pkg_manager = ""
    
    # check if debian system
    if (os.path.isfile("/etc/debian_version")):
        try:
            subprocess.check_output("command -v dpkg", shell=True)
            pkg_manager = "dpkg"
        except subprocess.CalledProcessError:
            pass
    # check if redhat system
    elif (os.path.isfile("/etc/redhat_version")):
        try:
            subprocess.check_output("command -v rpm", shell=True)
            pkg_manager = "rpm"
        except subprocess.CalledProcessError:
            pass

    # likely SUSE or modified VM, just check dpkg and rpm
    if (pkg_manager == ""):
        try:
            subprocess.check_output("command -v dpkg", shell=True)
            pkg_manager = "dpkg"
        except subprocess.CalledProcessError:
            try:
                subprocess.check_output("command -v rpm", shell=True)
                pkg_manager = "rpm"
            except subprocess.CalledProcessError:
                pass
    general_info['PKG_MANAGER'] = pkg_manager
    return pkg_manager

def get_package_version(pkg):
    pkg_mngr = geninfo_lookup('PKG_MANAGER')
    # dpkg
    if (pkg_mngr == 'dpkg'):
        return get_dpkg_pkg_version(pkg)
    # rpm
    elif (pkg_mngr == 'rpm'):
        return get_rpm_pkg_version(pkg)
    else:
        return (None, None)
    
# Package Info
def get_dpkg_pkg_version(pkg):
    try:
        dpkg_info = subprocess.check_output(['dpkg', '-s', pkg], universal_newlines=True,\
                                            stderr=subprocess.STDOUT)
        dpkg_lines = dpkg_info.split('\n')
        for line in dpkg_lines:
            if (line.startswith('Package: ') and not line.endswith(pkg)):
                # wrong package
                return (None, None)
            if (line.startswith('Status: ') and not line.endswith('installed')):
                # not properly installed
                return (None, None)
            if (line.startswith('Version: ')):
                version = (line.split())[-1]
                return (version, None)
        return (None, None)
    except subprocess.CalledProcessError as e:
        return (None, e.output)

def get_rpm_pkg_version(pkg):
    try:
        rpm_info = subprocess.check_output(['rpm', '-qi', pkg], universal_newlines=True,\
                                            stderr=subprocess.STDOUT)
        if ("package {0} is not installed".format(pkg) in rpm_info):
            # didn't find package
            return (None, None)
        rpm_lines = rpm_info.split('\n')
        for line in rpm_lines:
            parsed_line = line.split()
            if (parsed_line[0] == 'Name'):
                # ['Name', ':', name]
                name = parsed_line[2]
                if (name != pkg):
                    # wrong package
                    return (None, None)
            if (parsed_line[0] == 'Version'):
                # ['Version', ':', version]
                version = parsed_line[2]
                return (version, None)
        return (None, None)
    except subprocess.CalledProcessError as e:
        return (None, e.output)

def find_ama_version():
    """
    Gets a list of all AMA versions installed on the VM
    """
    try:
        config_dirs = filter((lambda x : x.startswith("Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-")), os.listdir("/var/lib/waagent"))
        ama_vers = list(map((lambda x : (x.split('-'))[-1]), config_dirs))
    except FileNotFoundError as e:
        return (None, e)
    return (ama_vers, None)


def check_ama_installed(ama_vers):
    """
    Checks to verify AMA is installed and only has one version installed at a time
    """
    ama_exists = ((ama_vers != None) and (len(ama_vers) > 0))
    ama_unique = (ama_exists and (len(ama_vers) == 1))
    return (ama_exists, ama_unique)

def run_cmd_output(cmd):
    """
    Common logic to run any command and check/get its output for further use
    """
    try:
        out = subprocess.check_output(cmd, shell=True, universal_newlines=True, stderr=subprocess.STDOUT)
        return out
    except subprocess.CalledProcessError as e:
        return (e.output)


def find_dcr_workspace():
    global general_info
    
    if 'DCR_WORKSPACE_ID' in general_info and 'DCR_REGION' in general_info:
        return (general_info['DCR_WORKSPACE_ID'], general_info['DCR_REGION'], None)
    dcr_workspace = set()
    dcr_region = set()
    me_region = set()
    general_info['URL_SUFFIX'] = '.com'
    try:
        for file in os.listdir(CONFIG_DIR):
            file_path = CONFIG_DIR + "/" + file
            with open(file_path) as f:
                result = json.load(f)
                channels = result['channels']
                for channel in channels:
                    if channel['protocol'] == 'ods':
                        # parse dcr workspace id
                        endpoint_url = channel['endpoint']
                        workspace_id = endpoint_url.split('https://')[1].split('.ods')[0]
                        dcr_workspace.add(workspace_id)
                        # parse dcr region
                        token_endpoint_uri = channel['tokenEndpointUri']
                        region = token_endpoint_uri.split('Location=')[1].split('&')[0]
                        dcr_region.add(region)
                        # parse url suffix
                        if '.us' in endpoint_url:
                            general_info['URL_SUFFIX'] = '.us'
                        if '.cn' in endpoint_url:
                            general_info['URL_SUFFIX'] = '.cn'                            
                    if channel['protocol'] == 'me':
                        # parse ME region
                        endpoint_url = channel['endpoint']
                        region = endpoint_url.split('https://')[1].split('.monitoring')[0]
                        me_region.add(region)
    except Exception as e:
        return (None, None, e)

    general_info['DCR_WORKSPACE_ID'] = dcr_workspace
    general_info['DCR_REGION'] = dcr_region
    general_info['ME_REGION'] = me_region
    return (dcr_workspace, dcr_region, None)

def find_dce():
    global general_info
    
    dce = set()
    try:
        for file in os.listdir(CONFIG_DIR):
            file_path = CONFIG_DIR + "/" + file
            with open(file_path) as f:
                result = json.load(f)
                channels = result['channels']
                for channel in channels:
                    if channel['protocol'] == 'gig':
                        # parse dce logs ingestion endpoint
                        ingest_endpoint_url = channel['endpointUriTemplate']
                        ingest_endpoint = ingest_endpoint_url.split('https://')[1].split('/')[0]
                        dce.add(ingest_endpoint)
                        # parse dce configuration access endpoint
                        configuration_endpoint_url = channel['tokenEndpointUri']
                        configuration_endpoint = configuration_endpoint_url.split('https://')[1].split('/')[0]
                        dce.add(configuration_endpoint)
    except Exception as e:
        return (None, None, e)

    general_info['DCE'] = dce
    return (dce, None)

def is_metrics_configured():
    global general_info
    if 'metrics' in general_info:
        return general_info['metrics']
    
    with open(METRICS_FILE) as f:
        output = f.read(2)
        if output != '[]':
            general_info['metrics'] = True
        else:
            general_info['metrics'] = False
    return general_info['metrics']
    
    
