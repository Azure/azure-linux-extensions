import os
import platform
import subprocess

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


def get_input(question, check_ans, no_fit):
    answer = input(" {0}: ".format(question))
    while (not check_ans(answer.lower())):
        print("Unclear input. {0}".format(no_fit))
        answer = input(" {0}: ".format(question))
    return answer


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
                    elif line.startswith('VERSION_ID='):
                        vm_ver = line.split('=')[1]
                        vm_ver = vm_ver.replace('\"', '').replace('\n', '')
        except:  # indeterminate OS
            return None, None
    return vm_dist.lower(), vm_ver.lower()


def find_package_manager():
    """
    Checks which package manager is on the system
    """
    pkg_manager = ""
    
    # check if debian system
    if (os.path.isfile("/etc/debian_version")):
        try:
            subprocess.check_call("command -v dpkg", shell=True, stdout=DEVNULL)
            pkg_manager = "dpkg"
        except subprocess.CalledProcessError:
            pass
    # check if redhat system
    elif (os.path.isfile("/etc/redhat_version")):
        try:
            subprocess.check_call("command -v rpm", shell=True, stdout=DEVNULL)
            pkg_manager = "rpm"
        except subprocess.CalledProcessError:
            pass

    # likely SUSE or modified VM, just check dpkg and rpm
    if (pkg_manager == ""):
        try:
            subprocess.check_call("command -v dpkg", shell=True, stdout=DEVNULL)
            pkg_manager = "dpkg"
        except subprocess.CalledProcessError:
            try:
                subprocess.check_call("command -v rpm", shell=True, stdout=DEVNULL)
                pkg_manager = "rpm"
            except subprocess.CalledProcessError:
                pass

    return pkg_manager


def find_ama_version():
    """
    Gets a list of all AMA versions installed on the VM
    """
    config_dirs = filter((lambda x : x.startswith("Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-")), os.listdir("/var/lib/waagent"))
    ama_vers = list(map((lambda x : (x.split('-'))[-1]), config_dirs))
    return ama_vers


def check_ama_installed(ama_vers):
    """
    Checks to verify AMA is installed and only has one version installed at a time
    """
    ama_installed_vers = ama_vers
    ama_exists = (len(ama_installed_vers) > 0)
    ama_unique = (len(ama_installed_vers) == 1)
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


#TODO: parse /etc/opt/microsoft/azuremonitoragent/config-cache/configchunks.*.json for workspace ID and VM region
def find_wkspc_id():
    return None


def find_vm_region():
    return None
