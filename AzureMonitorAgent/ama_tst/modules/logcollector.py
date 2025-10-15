import datetime
import os
import platform
import shutil
import json

import helpers
from error_codes        import *
from connect.check_imds import check_metadata


DPKG_CMD = "dpkg -s azuremonitoragent"
RPM_CMD = "rpm -qi azuremonitoragent"
PS_CMD = "ps -ef | grep {0} | grep -v grep"
OPENSSL_CMD = "echo | openssl s_client -connect {0}:443 -brief"
SYSTEMCTL_CMD = "systemctl status {0} --no-pager"
JOURNALCTL_CMD = "journalctl -u {0} --no-pager --since \"30 days ago\" > {1}"
PS_CMD_CPU = "ps aux --sort=-pcpu | head -10"
PS_CMD_RSS = "ps aux --sort -rss | head -10"
PS_CMD_VSZ = "ps aux --sort -vsz | head -10"
DU_CMD = "du -h -d 1 {0} /var/opt/microsoft/azuremonitoragent/events"
VAR_DU_CMD = "du -h -d 1 {0} /var"
LS_CMD = "ls -al {0}"
NAMEI_CMD = "namei -om {0}"
TAIL_SYSLOG_CMD = "tail -10000 /var/log/{0} > {1}"
ArcSettingsFile = '/var/opt/azcmagent/localconfig.json'
PERMISSION_CHECK_FILES = ["/etc/opt/microsoft/azuremonitoragent/config-cache",
                            "/etc/opt/microsoft/azuremonitoragent",
                            "/var/opt/microsoft/azuremonitoragent",
                            "/var/run/azuremonitoragent",
                            "/opt/microsoft/azuremonitoragent",
                            "/run/azuremonitoragent",
                            "/var/lib/waagent/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-*"]


# File copying functions

def copy_file(src, dst):
    if (os.path.isfile(src)):
        print("Copying file {0}".format(src))
        try:
            if (not os.path.isdir(dst)):
                os.mkdir(dst)
            shutil.copy2(src, dst)
        except Exception as e:
            print("ERROR: Could not copy {0}: {1}".format(src, e))
            print("Skipping over file {0}".format(src))
    else:
        print("File {0} doesn't exist, skipping".format(src))
    return


def copy_dircontents(src, dst):
    if (os.path.isdir(src)):
        print("Copying contents of directory {0}".format(src))
        try:
            shutil.copytree(src, dst)
            auth_token_path = os.path.join(dst, "metrics_configs", "AuthToken-MSI.json")
            if (os.path.isfile(auth_token_path)):
                print("Found AuthToken-MSI.json")
                try:
                    with open(auth_token_path, 'r') as auth_token:
                        auth_token_json = json.load(auth_token)
                    if (auth_token_json and "access_token" in auth_token_json):
                        print("Removing access_token value from AuthToken-MSI.json")
                        auth_token_json["access_token"] = ""
                        with open(auth_token_path, 'w') as auth_token:
                            json.dump(auth_token_json, auth_token, indent=4)
                        print("Successfully removed access_token value from AuthToken-MSI.json")
                except Exception as e:
                    print("ERROR: Could not decode JSON from {0}: {1}".format(auth_token_path, e))
        except Exception as e:
            print("ERROR: Could not copy {0}: {1}".format(src, e))
            print("Skipping over contents of directory {0}".format(src))
    else:
        print("Directory {0} doesn't exist, skipping".format(src))
    return




# Log collecting functions

def collect_process_environ(output_dirpath, process_name, outfile_handle=None):
    """
    Collect environment variables for a specific process.
    If outfile_handle is provided, writes to that file handle (for main log).
    If outfile_handle is None, creates a separate file in the process directory.
    """
    
    if outfile_handle is None:
        # Create separate file mode
        process_dir = os.path.join(output_dirpath, process_name)
        if not os.path.isdir(process_dir):
            os.makedirs(process_dir)
        
        environ_file_path = os.path.join(process_dir, "{0}_environ.txt".format(process_name))
        
        try:
            with open(environ_file_path, 'w') as environ_file:
                _write_process_environ_data(environ_file, process_name, separate_file=True)
            print("{0} environment variables saved to {1}".format(process_name.upper(), environ_file_path))
        except Exception as e:
            print("ERROR: Could not create {0} environment variables file: {1}".format(process_name, e))
    else:
        # Write to existing file handle mode (for main log)
        _write_process_environ_data(outfile_handle, process_name, separate_file=False)


def _write_process_environ_data(file_handle, process_name, separate_file=True):
    """Helper function to write process environment data to a file handle"""
    if separate_file:
        # Format for separate file
        file_handle.write("{0} Environment Variables Collection\n".format(process_name.upper()))
        file_handle.write("=====================================\n")
        file_handle.write("Collected on: {0}\n\n".format(datetime.datetime.utcnow().isoformat()))
    else:
        # Format for main log file
        file_handle.write("{0} Environment Variables:\n".format(process_name.upper()))
        file_handle.write("========================================\n")
    
    # Get all process PIDs
    process_pids_output = helpers.run_cmd_output("pidof {0}".format(process_name))
    if process_pids_output.strip():
        process_pids = process_pids_output.strip().split()
        for pid in process_pids:
            file_handle.write("PID: {0}\n".format(pid))
            environ_path = "/proc/{0}/environ".format(pid)
            if os.path.isfile(environ_path):
                try:
                    with open(environ_path, 'rb') as proc_environ_file:
                        environ_data = proc_environ_file.read()
                        # Convert null-separated variables to readable format
                        # Use try/except for Python 2/3 compatibility with decode errors parameter
                        try:
                            environ_vars = environ_data.decode('utf-8', errors='replace').replace('\x00', '')
                        except TypeError:
                            # Python 2.6 doesn't support errors parameter
                            environ_vars = environ_data.decode('utf-8').replace('\x00', '')
                        file_handle.write("{0}\n".format(environ_vars))
                except Exception as e:
                    file_handle.write("Error reading environment variables for PID {0}: {1}\n".format(pid, e))
            else:
                file_handle.write("Environment file not found for PID {0}\n".format(pid))
            file_handle.write("=====================================\n")
    else:
        file_handle.write("No {0} processes found\n".format(process_name))
    
    if not separate_file:
        # Add separator for main log file
        file_handle.write("--------------------------------------------------------------------------------\n")

def collect_logs(output_dirpath, pkg_manager):
    # collect MDSD information
    copy_file("/etc/default/azuremonitoragent", os.path.join(output_dirpath,"mdsd"))
    copy_file("/var/opt/microsoft/azuremonitoragent/events/taskstate.json", os.path.join(output_dirpath,"mdsd"))
    copy_dircontents("/var/opt/microsoft/azuremonitoragent/log", os.path.join(output_dirpath,"mdsd","logs"))
    # collect MDSD environment variables
    collect_process_environ(output_dirpath, "mdsd")
    # collect AMA Core Agent environment variables
    collect_process_environ(output_dirpath, "amacoreagent")
    # collect AMA DCR
    copy_dircontents("/etc/opt/microsoft/azuremonitoragent", os.path.join(output_dirpath,"DCR"))

    # get all AzureMonitorLinuxAgent-* directory names
    for config_dir in filter((lambda x : x.startswith("Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-")), os.listdir("/var/lib/waagent")):
        # collect AMA config and status information for all AzureMonitorLinuxAgent-* directories
        ver = (config_dir.split('-'))[-1]
        copy_dircontents(os.path.join("/var/lib/waagent",config_dir,"status"), os.path.join(output_dirpath,ver+"-status"))
        copy_dircontents(os.path.join("/var/lib/waagent",config_dir,"config"), os.path.join(output_dirpath,ver+"-config"))

    # collect system logs
    system_logs = ""
    if (pkg_manager == "dpkg"):
        system_logs = "syslog"
    elif (pkg_manager == "rpm"):
        system_logs = "messages"
    if (system_logs != ""):
        for systemlog_file in filter((lambda x : x.startswith(system_logs)), os.listdir("/var/log")):
            helpers.run_cmd_output(TAIL_SYSLOG_CMD.format(systemlog_file, os.path.join(output_dirpath,"system_logs")))

    # collect rsyslog information (if present)
    copy_file("/etc/rsyslog.conf", os.path.join(output_dirpath,"rsyslog"))
    copy_dircontents("/etc/rsyslog.d", os.path.join(output_dirpath,"rsyslog","rsyslog.d"))
    if (os.path.isfile("/etc/rsyslog.conf")):
        helpers.run_cmd_output(JOURNALCTL_CMD.format("rsyslog", os.path.join(output_dirpath,"rsyslog","journalctl_output.log")))
    # collect syslog-ng information (if present)
    copy_dircontents("/etc/syslog-ng", os.path.join(output_dirpath,"syslog-ng"))

    return


def collect_arc_logs(output_dirpath, pkg_manager):
    # collect GC Extension logs
    copy_dircontents("/var/lib/GuestConfig/ext_mgr_logs", os.path.join(output_dirpath,"GC_Extension"))
    # collect AMA Extension logs
    for config_dir in filter((lambda x : x.startswith("Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-")), os.listdir("/var/lib/GuestConfig/extension_logs")):
        # collect AMA config and status information for all AzureMonitorLinuxAgent-* directories
        ver = (config_dir.split('-'))[-1]
        copy_dircontents(os.path.join("/var/lib/GuestConfig/extension_logs",config_dir), os.path.join(output_dirpath,ver+"-extension_logs"))

    copy_file(ArcSettingsFile, os.path.join(output_dirpath,"Arc"))
    
    # collect logs same to both Arc + Azure VM
    collect_logs(output_dirpath, pkg_manager)

    print("Arc logs collected")
    return


def collect_azurevm_logs(output_dirpath, pkg_manager):
    # collect waagent logs
    for waagent_file in filter((lambda x : x.startswith("waagent.log")), os.listdir("/var/log")):
        copy_file(os.path.join("/var/log",waagent_file), os.path.join(output_dirpath,"waagent"))
    # collect AMA Extension logs
    copy_dircontents("/var/log/azure/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent", os.path.join(output_dirpath,"Microsoft.Azure.Monitor.AzureMonitorLinuxAgent"))
    
    # collect logs same to both Arc + Azure VM
    collect_logs(output_dirpath, pkg_manager)

    print("Azure VM logs collected")
    return



# Outfile function
    
def create_outfile(output_dirpath, logs_date, pkg_manager):
    with open(os.path.join(output_dirpath,"amalinux.out"), 'w') as outfile:
        outfile.write("Log Collection Start Time: {0}\n".format(logs_date))
        outfile.write("--------------------------------------------------------------------------------\n")

        # detected OS + version
        vm_dist, vm_ver, _ = helpers.find_vm_distro()
        if (vm_dist and vm_ver):
            outfile.write("Linux OS detected: {0}\n".format(vm_dist))
            outfile.write("Linux OS version detected: {0}\n".format(vm_ver))
        else:
            outfile.write("Indeterminate OS.\n")

        # detected package manager
        if (pkg_manager != ""):
            outfile.write("Package manager detected: {0}\n".format(pkg_manager))
        else:
            outfile.write("Indeterminate package manager.\n")
        outfile.write("--------------------------------------------------------------------------------\n")

        # uname info
        os_uname = os.uname()
        outfile.write("Hostname: {0}\n".format(os_uname[1]))
        outfile.write("Release Version: {0}\n".format(os_uname[2]))
        outfile.write("Linux UName: {0}\n".format(os_uname[3]))
        outfile.write("Machine Type: {0}\n".format(os_uname[4]))
        outfile.write("--------------------------------------------------------------------------------\n")

        # python version
        outfile.write("Python Version: {0}\n".format(platform.python_version()))
        outfile.write("--------------------------------------------------------------------------------\n")
        
        # /etc/os-release
        if (os.path.isfile("/etc/os-release")):
            outfile.write("Contents of /etc/os-release:\n")
            with open("/etc/os-release", 'r') as os_info:
                for line in os_info:
                    outfile.write(line)
            outfile.write("--------------------------------------------------------------------------------\n")

        # VM Metadata
        attributes = ['azEnvironment', 'resourceId', 'location']
        outfile.write("VM Metadata from IMDS:\n")
        for attr in attributes:
            attr_result = helpers.geninfo_lookup(attr)
            if (not attr_result) and (check_metadata() == NO_ERROR):
                attr_result = helpers.geninfo_lookup(attr)
            if (attr_result != None):
                outfile.write("{0}: {1}\n".format(attr, attr_result))
        outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")

 
        # AMA install status
        (ama_vers, _) = helpers.find_ama_version()
        (ama_installed, ama_unique) = helpers.check_ama_installed(ama_vers)
        outfile.write("AMA Install Status: {0}\n".format("installed" if ama_installed else "not installed"))
        if (ama_installed):
            if (not ama_unique):
                outfile.write("Multiple AMA versions detected: {0}\n".format(', '.join(ama_vers)))
            else:
                outfile.write("AMA Version: {0}\n".format(ama_vers[0]))
        outfile.write("--------------------------------------------------------------------------------\n")

        # connection to endpoints
        wkspc_id, wkspc_region, agent_settings, e = helpers.find_dcr_workspace()
        if e == None:
            outfile.write("Workspace ID: {0}\n".format(str(wkspc_id)))
            outfile.write("Workspace region: {0}\n".format(str(wkspc_region)))
            outfile.write("--------------------------------------------------------------------------------\n")
            if agent_settings != {}:
                outfile.write("AgentSettinsgs file found: {0}\n".format(str(agent_settings)))

        # AMA package info (dpkg/rpm)
        if (pkg_manager == "dpkg"):
            outfile.write("Output of command: {0}\n".format(DPKG_CMD))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(DPKG_CMD))
            outfile.write("--------------------------------------------------------------------------------\n")
        elif (pkg_manager == "rpm"):
            outfile.write("Output of command: {0}\n".format(RPM_CMD))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(RPM_CMD))
            outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")

        # ps -ef output
        for process in ["azuremonitoragent", "mdsd", "telegraf"]:
            ps_process_cmd = PS_CMD.format(process)
            outfile.write("Output of command: {0}\n".format(ps_process_cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(ps_process_cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
        
        # process environment variables output
        collect_process_environ(output_dirpath, "mdsd", outfile)
        collect_process_environ(output_dirpath, "amacoreagent", outfile)

        # rsyslog / syslog-ng status via systemctl
        for syslogd in ["rsyslog", "syslog-ng"]:
            systemctl_cmd = SYSTEMCTL_CMD.format(syslogd)
            outfile.write("Output of command: {0}\n".format(systemctl_cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(systemctl_cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")

        # ps aux output
        for cmd in [PS_CMD_CPU, PS_CMD_RSS, PS_CMD_VSZ]:
            outfile.write("Output of command: {0}\n".format(cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")

        # du output on events folder
        for flag in ["", "--apparent-size"]:
            du_full_cmd = DU_CMD.format(flag)
            outfile.write("Output of command: {0}\n".format(du_full_cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(du_full_cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")

        # du output on /var folder
        for flag in ["", "--apparent-size"]:
            du_full_cmd = VAR_DU_CMD.format(flag)
            outfile.write("Output of command: {0}\n".format(du_full_cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(du_full_cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
            
        # file permission check
        for file in PERMISSION_CHECK_FILES:
            file_permission_cmd = LS_CMD.format(file)
            outfile.write("Output of command: {0}\n".format(file_permission_cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(file_permission_cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")
        
        # parent directory permission check
        for file in PERMISSION_CHECK_FILES:
            dir_permission_cmd = NAMEI_CMD.format(file)
            outfile.write("Output of command: {0}\n".format(dir_permission_cmd))
            outfile.write("========================================\n")
            outfile.write(helpers.run_cmd_output(dir_permission_cmd))
            outfile.write("--------------------------------------------------------------------------------\n")
        outfile.write("--------------------------------------------------------------------------------\n")






### MAIN FUNCTION BODY BELOW ###



def run_logcollector(output_location):
    # check if Arc is being used
    is_arc_vm = helpers.is_arc_installed()

    # create directory to hold copied logs
    vm_type = "azurearc" if is_arc_vm else "azurevm"
    logs_date = str(datetime.datetime.utcnow().isoformat()).replace(":", ".")  # ':' causes issues with tar
    output_dirname = "amalogs-{0}-{1}".format(vm_type, logs_date)
    output_dirpath = os.path.join(output_location, output_dirname)
    try:
        os.mkdir(output_dirpath)
    except OSError as e:
        print("ERROR: Could not create output directory: {0}".format(e))
        return

    # get VM information needed for log collection
    pkg_manager = helpers.find_package_manager()

    # collect the logs
    if (is_arc_vm):
        print("Azure Arc detected, collecting logs for Azure Arc.")
        print("--------------------------------------------------------------------------------")
        collect_arc_logs(output_dirpath, pkg_manager)
    else:
        print("Azure Arc not detected, collected logs for Azure VM.")
        print("--------------------------------------------------------------------------------")
        collect_azurevm_logs(output_dirpath, pkg_manager)
    print("--------------------------------------------------------------------------------")

    # create out file (for simple checks)
    print("Creating 'amalinux.out' file")
    create_outfile(output_dirpath, logs_date, pkg_manager)
    print("--------------------------------------------------------------------------------")

    # zip up logs
    print("Zipping up logs and removing temporary output directory")
    tgz_filename = "{0}.tgz".format(output_dirname)
    tgz_filepath = os.path.join(output_location, tgz_filename)
    print("--------------------------------------------------------------------------------")
    print(helpers.run_cmd_output("cd {0}; tar -zcf {1} {2}".format(output_location, tgz_filename, output_dirname)))
    # This makes archive not readable by anyone else but the user who created it
    print("Setting permissions on the archive to 600 so only the user who created it can read it")
    print("--------------------------------------------------------------------------------")
    os.chmod(tgz_filepath, 0o600)
    shutil.rmtree(output_dirpath, ignore_errors=True)

    print("--------------------------------------------------------------------------------")
    print("You can find the AMA logs at the following location: {0}".format(tgz_filepath))
    return
