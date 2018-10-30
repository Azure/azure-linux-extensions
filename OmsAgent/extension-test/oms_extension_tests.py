"""
Test the OMS Agent on all or a subset of images.

Setup: read parameters and setup HTML report
Test:
1. Create vm and install agent
2. Wait for data to propagate to backend and check for data
3. Remove extension
4. Reinstall extension
5. Optionally, wait for hours and check data and extension status
6. Purge extension and delete vm
Finish: compile HTML report and log file
"""

import json
import os
import os.path
import subprocess
import re
import sys
import time
import rstr

from platform import system
from collections import OrderedDict
from verify_e2e import check_e2e

from json2html import *

E2E_DELAY = 10 # Delay (minutes) before checking for data
LONG_DELAY = 250 # Delay (minutes) before rechecking extension

images_list = { 'ubuntu14': 'Canonical:UbuntuServer:14.04.5-LTS:14.04.201808180',
         'ubuntu16': 'Canonical:UbuntuServer:16.04-LTS:latest',
         'ubuntu18': 'Canonical:UbuntuServer:18.04-LTS:latest',
         'debian8': 'credativ:Debian:8:latest',
         'debian9': 'credativ:Debian:9:latest',
         'redhat6': 'RedHat:RHEL:6.9:latest',
         'redhat7': 'RedHat:RHEL:7.3:latest',
         'centos6': 'OpenLogic:CentOS:6.9:latest',
         'centos7': 'OpenLogic:CentOS:7.5:latest',
         'oracle6': 'Oracle:Oracle-Linux:6.9:latest',
         'oracle7': 'Oracle:Oracle-Linux:7.5:latest',
         'suse12': 'SUSE:SLES:12-SP2:latest'}

vmnames = []

if len(sys.argv) == 1:
    print(('Please indicate run length (short or long) and optional image subset:\n'
           '$ python -u oms_extension_tests.py length [image...]'))
is_long = sys.argv[1] == 'long'

if len(sys.argv) > 2:
    vms_list = sys.argv[2:]
    images = {}
    for vm in vms_list:
        vm_dict = { vm: images_list[vm] }
        images.update(vm_dict)
else:
    images = images_list

with open('{0}/parameters.json'.format(os.getcwd()), 'r') as f:
    parameters = f.read()
    if re.search(r'"<.*>"', parameters):
        print('Please replace placeholders in parameters.json')
        exit()
    parameters = json.loads(parameters)

resource_group = parameters['resource group']
location = parameters['location']
username = parameters['username']
password = parameters['password']
nsg_group = parameters['nsg group']
nsg_resource_group = parameters['nsg resource group']
size = parameters['size'] # Preferred: 'Standard_B1ms'
extension = parameters['extension'] # OmsAgentForLinux
publisher = parameters['publisher'] # Microsoft.EnterpriseCloud.Monitoring
key_vault = parameters['key vault']
subscription = str(json.loads(subprocess.check_output('az keyvault secret show --name subscription-id --vault-name {0}'.format(key_vault), shell=True))["value"])
workspace_id = str(json.loads(subprocess.check_output('az keyvault secret show --name workspace-id --vault-name {0}'.format(key_vault), shell=True))["value"])
workspace_key = str(json.loads(subprocess.check_output('az keyvault secret show --name workspace-key --vault-name {0}'.format(key_vault), shell=True))["value"])
public_settings = { "workspaceId": workspace_id }
private_settings = { "workspaceKey": workspace_key }
nsg = "/subscriptions/"+ subscription + "/resourceGroups/" + nsg_resource_group + "/providers/Microsoft.Network/networkSecurityGroups/" + nsg_group

# Detect the host system and validate nsg
if system() == 'Windows':
    if os.system('az network nsg show --resource-group {0} --name {1} --query "[?n]"'.format(nsg_resource_group, nsg_group)) == 0:
        print "Network Security Group successfully validated"
elif system() == 'Linux':
    if os.system('az network nsg show --resource-group {0} --name {1} > /dev/null 2>&1'.format(nsg_resource_group, nsg_group)) == 0:
        print "Network Security Group successfully validated"
else:
    print("""Please verify that the nsg or nsg resource group are valid and are in the right subscription.
If there is no Network Security Group, please create new one. NSG is a must to create a VM in this testing.""")
    exit()


result_html_file = open("finalresult.html", 'a+')

# Common logic to save command itself
def write_log_command(log, cmd):
    print(cmd)
    log.write(cmd + '\n')
    log.write('-' * 40)
    log.write('\n')

# Common logic to append a file to another
def append_file(src, dest):
    f = open(src, 'r')
    dest.write(f.read())
    f.close()

# Common logic to replace string in a file
def replace_items(infile,old_word,new_word):
    if not os.path.isfile(infile):
        print "Error on replace_word, not a regular file: "+infile
        sys.exit(1)

    f1=open(infile,'r').read()
    f2=open(infile,'w')
    m=f1.replace(old_word,new_word)
    f2.write(m)

# Secure copy required files from local to vm
def copy_to_vm(dnsname, username, password, location):
    os.system("echo y | pscp -pw {} -r omsfiles/* {}@{}.{}.cloudapp.azure.com:/tmp/".format(password, username, dnsname.lower(), location))

# Secure copy files from vm to local
def copy_from_vm(dnsname, username, password, location, filename):
    os.system("echo y | pscp -pw {} -r {}@{}.{}.cloudapp.azure.com:/home/scratch/{} .".format(password, username, dnsname.lower(), location, filename))

# Run scripts on vm using AZ CLI
def run_command(resource_group, vmname, commandid, script):
    os.system('az vm run-command invoke -g {} -n {} --command-id {} --scripts "{}"'.format(resource_group, vmname, commandid, script))

# Create vm using AZ CLI
def create_vm(resource_group, vmname, image, username, password, location, dnsname, vmsize, networksecuritygroup):
    os.system('az vm create -g {} -n {} --image {} --admin-username {} --admin-password {} --location {} --public-ip-address-dns-name {} --size {} --nsg {}'.format(resource_group, vmname, image, username, password, location, dnsname, vmsize, networksecuritygroup))

# Add extension to vm using AZ CLI
def add_extension(extension, publisher, vmname, resource_group, private_settings, public_settings):
    os.system('az vm extension set -n {} --publisher {} --vm-name {} --resource-group {} --protected-settings "{}" --settings "{}"'.format(extension, publisher, vmname, resource_group, private_settings, public_settings))

# Delete extension from vm using AZ CLI
def delete_extension(extension, vmname, resource_group):
    os.system('az vm extension delete -n {} --vm-name {} --resource-group {}'.format(extension, vmname, resource_group))

# Get vm details using AZ CLI
def get_vm_resources(resource_group, vmname):
    vm_cli_out = json.loads(subprocess.check_output('az vm show -g {0} -n {1} --debug'.format(resource_group, vmname), shell=True))
    os_disk = vm_cli_out['storageProfile']['osDisk']['name']
    nic_name = vm_cli_out['networkProfile']['networkInterfaces'][0]['id'].split('/')[-1]
    ip_list = json.loads(subprocess.check_output('az vm list-ip-addresses -n {0} -g {1} --debug'.format(vmname, resource_group), shell=True))
    ip_name = ip_list[0]['virtualMachine']['network']['publicIpAddresses'][0]['name']
    return os_disk, nic_name, ip_name

# Delete vm using AZ CLI
def delete_vm(resource_group, vmname):
    os.system('az vm delete -g {} -n {} --yes'.format(resource_group, vmname))

# Delete vm disk using AZ CLI
def delete_vm_disk(resource_group, os_disk):
    os.system('az disk delete --resource-group {0} --name {1} --yes --debug'.format(resource_group, os_disk))

# Delete vm network interface using AZ CLI
def delete_nic(resource_group, nic_name):
    os.system('az network nic delete --resource-group {0} --name {1} --no-wait --debug'.format(resource_group, nic_name))

# Delete vm ip from AZ CLI
def delete_ip(resource_group, ip_name):
    os.system('az network public-ip delete --resource-group {0} --name {1}'.format(resource_group, ip_name))


htmlstart="""<!DOCTYPE html>
<html>
<head>
<style>
table {
    font-family: arial, sans-serif;
    border-collapse: collapse;
    width: 100%;
}

table:not(th) {
    font-weight: lighter;
}

td, th {
    border: 1px solid #dddddd;
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {
    background-color: #dddddd;
}
</style>
</head>
<body>
"""
result_html_file.write(htmlstart)

def main():
    """Orchestrate fundemental testing steps onlined in header docstring."""
    install_oms_msg = create_vm_and_install_extension()
    verify_oms_msg = verify_data()
    remove_oms_msg = remove_extension()
    reinstall_oms_msg = reinstall_extension()
    if is_long:
        time.sleep(LONG_DELAY)
        long_verify_msg = verify_data()
        long_status_msg = check_status()
    else:
        long_verify_msg, long_status_msg = None, None
    remove_extension_and_delete_vm()
    messages = (install_oms_msg, verify_oms_msg, remove_oms_msg,
                reinstall_oms_msg, long_verify_msg, long_status_msg)
    create_report(messages)


def create_vm_and_install_extension():
    """Create vm and install the extension, returning HTML results."""

    message = ""
    for distname, image in images.iteritems():
        uid = rstr.xeger(r'[0-9a-f]{8}')
        vmname = distname.lower() + '-' + uid
        vmnames.append(vmname)
        dnsname = vmname
        vm_log_file = distname.lower() + "result.log"
        vm_html_file = distname.lower() + "result.html"
        log_open = open(vm_log_file, 'a+')
        html_open = open(vm_html_file, 'a+')
        print "\nCreate VM and Install Extension - {}: {} \n".format(vmname, image)
        create_vm(resource_group, vmname, image, username, password, location, dnsname, size, nsg)
        copy_to_vm(dnsname, username, password, location)
        delete_extension(extension, vmname, resource_group)
        run_command(resource_group, vmname, 'RunShellScript', 'python -u /tmp/oms_extension_run_script.py -preinstall')
        add_extension(extension, publisher, vmname, resource_group, private_settings, public_settings)
        run_command(resource_group, vmname, 'RunShellScript', 'python -u /home/scratch/oms_extension_run_script.py -postinstall')
        copy_from_vm(dnsname, username, password, location, 'omsresults.*')
        write_log_command(log_open, 'Status After Creating VM and Adding OMS Extension')
        html_open.write('<h1 id="{0}"> VM: {0} <h1>'.format(distname))
        html_open.write("<h2> Install OMS Agent </h2>")
        append_file('omsresults.log', log_open)
        append_file('omsresults.html', html_open)
        log_open.close()
        html_open.close()
        status = open('omsresults.status', 'r').read()
        if status == "Agent Found":
            message += """
                            <td><span style='background-color: #66ff99'>Install Success</span></td>"""
        elif status == "Onboarding Failed":
            message += """
                            <td><span style='background-color: red; color: white'>Onboarding Failed</span></td>"""
        elif status == "Agent Not Found":
            message += """
                            <td><span style='background-color: red; color: white'>Install Failed</span></td>"""
    return message

def verify_data():
    """Verify data end-to-end, returning HTML results."""
    # Delay to allow data to propagate
    for i in reversed(range(1, E2E_DELAY + 1)):
        print('E2E propagation delay: T-{} Minutes'.format(i))
        time.sleep(60)

    message = ""
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        vm_log_file = distname + "result.log"
        vm_html_file = distname + "result.html"
        log_open = open(vm_log_file, 'a+')
        html_open = open(vm_html_file, 'a+')
        os.system('rm e2eresults.json')
        check_e2e(vmname)

        # write detailed table for vm
        html_open.write("<h2> Verify Data from OMS workspace </h2>")
        write_log_command(log_open, 'Status After Verifying Data')
        with open('e2eresults.json', 'r') as infile:
            data = json.load(infile)
        results = data[distname][0]
        log_open.write(distname + ':\n' + json.dumps(results, indent=4, separators=(',', ': ')) + '\n')
        # prepend distro column to results row before generating the table
        data = [OrderedDict([('Distro', distname)] + results.items())]
        out = json2html.convert(data)
        html_open.write(out)

        # write to summary table
        from verify_e2e import success_count
        if success_count == 6:
            message += """
                            <td><span style='background-color: #66ff99'>Verify Success</td>"""
        elif 0 < success_count < 6:
            from verify_e2e import success_sources, failed_sources
            message += """
                            <td><span style='background-color: #66ff99'>{0} Success</span> <br><br><span style='background-color: red; color: white'>{1} Failed</span></td>""".format(', '.join(success_sources), ', '.join(failed_sources))
        elif success_count == 0:
            message += """
                            <td><span style='background-color: red; color: white'>Verify Failed</span></td>"""
    return message

def remove_extension():
    """Remove the extension, returning HTML results."""

    message = ""
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        vm_log_file = distname + "result.log"
        vm_html_file = distname + "result.html"
        log_open = open(vm_log_file, 'a+')
        html_open = open(vm_html_file, 'a+')
        dnsname = vmname
        print "\nRemove Extension: {} \n".format(vmname)
        delete_extension(extension, vmname, resource_group)
        run_command(resource_group, vmname, 'RunShellScript', 'python -u /home/scratch/oms_extension_run_script.py -status')
        copy_from_vm(dnsname, username, password, location, 'omsresults.*')
        write_log_command(log_open, 'Status After Removing OMS Extension')
        html_open.write('<h2> Remove Extension: {0} <h2>'.format(vmname))
        append_file('omsresults.log', log_open)
        append_file('omsresults.html', html_open)
        log_open.close()
        html_open.close()
        status = open('omsresults.status', 'r').read()
        if status == "Agent Found":
            message += """
                            <td><span style="background-color: red; color: white">Remove Failed</span></td>"""
        elif status == "Onboarding Failed":
            message += """
                            <td><span style="background-color: red; color: white">Onboarding Failed</span></td>"""
        elif status == "Agent Not Found":
            message += """
                            <td><span style="background-color: #66ff99">Remove Success</span></td>"""
    return message


def reinstall_extension():
    """Reinstall the extension, returning HTML results."""

    message = ""
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        vm_log_file = distname + "result.log"
        vm_html_file = distname + "result.html"
        log_open = open(vm_log_file, 'a+')
        html_open = open(vm_html_file, 'a+')
        dnsname = vmname
        print "\n Reinstall Extension: {} \n".format(vmname)
        add_extension(extension, publisher, vmname, resource_group, private_settings, public_settings)
        run_command(resource_group, vmname, 'RunShellScript', 'python -u /home/scratch/oms_extension_run_script.py -postinstall')
        copy_from_vm(dnsname, username, password, location, 'omsresults.*')
        write_log_command(log_open, 'Status After Reinstall OMS Extension')
        html_open.write('<h2> Reinstall Extension: {0} <h2>'.format(vmname))
        append_file('omsresults.log', log_open)
        append_file('omsresults.html', html_open)
        log_open.close()
        html_open.close()
        status = open('omsresults.status')
        if status == "Agent Found":
            message += """
                            <td><span style='background-color: #66ff99'>Reinstall Success</span></td>"""
        elif status == "Onboarding Failed":
            message += """
                            <td><span style='background-color: red; color: white'>Onboarding Failed</span></td>"""
        elif status == "Agent Not Found":
            message += """
                            <td><span style='background-color: red; color: white'>Reinstall Failed</span></td>"""
    return message

def check_status():
    """Check agent status."""

    message = ""
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        vm_log_file = distname + "result.log"
        vm_html_file = distname + "result.html"
        log_open = open(vm_log_file, 'a+')
        html_open = open(vm_html_file, 'a+')
        dnsname = vmname
        print "\n Checking Status: {0} \n".format(vmname)
        run_command(resource_group, vmname, 'RunShellScript', 'python -u /home/scratch/oms_extension_run_script.py -status')
        copy_from_vm(dnsname, username, password, location, 'omsresults.*')
        write_log_command(log_open, 'Status After Long Run OMS Extension')
        html_open.write('<h2> Status After Long Run OMS Extension: {0} <h2>'.format(vmname))
        append_file('omsresults.log', log_open)
        append_file('omsresults.html', html_open)
        log_open.close()
        html_open.close()
        status = open('omsresults.status')
        if status == "Agent Found":
            message += """
                            <td><span style='background-color: #66ff99'>Reinstall Success</span></td>"""
        elif status == "Onboarding Failed":
            message += """
                            <td><span style='background-color: red; color: white'>Onboarding Failed</span></td>"""
        elif status == "Agent Not Found":
            message += """
                            <td><span style='background-color: red; color: white'>Reinstall Failed</span></td>"""
    return message

def remove_extension_and_delete_vm():
    """Remove extension and delete vm."""
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        vm_log_file = distname + "result.log"
        log_open = open(vm_log_file, 'a+')
        dnsname = vmname
        print "\n Remove extension and Delete VM: {} \n".format(vmname)
        delete_extension(extension, vmname, resource_group)
        run_command(resource_group, vmname, 'RunShellScript', 'python -u /home/scratch/oms_extension_run_script.py -copyextlogs')
        copy_from_vm(dnsname, username, password, location, '{0}-extension.log'.format(distname))
        disk, nic, ip = get_vm_resources(resource_group, vmname)
        delete_vm(resource_group, vmname)
        delete_vm_disk(resource_group, disk)
        delete_nic(resource_group, nic)
        delete_ip(resource_group, ip)
        append_file('{0}-extension.log'.format(distname), log_open)
        log_open.close()

def create_report(messages):
    """Compile the final HTML report."""
    install_oms_msg, verify_oms_msg, remove_oms_msg, reinstall_oms_msg, long_verify_msg, long_status_msg = messages
    result_log_file = open("finalresult.log", "a+")

    # summary table
    diststh = ""
    resultsth = ""
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        diststh += """
                <th>{0}</th>""".format(distname)
        resultsth += """
                <th><a href='#{0}'>{0} results</a></th>""".format(distname)
    
    # pre-compile long-running summary
    if long_verify_msg and long_status_msg:
        long_running_summary = """
        <tr>
          <td>Long-term Verify Data</td>
          {0}
        </tr>
        <tr>
          <td>Long-term Status</td>
          {1}
        </tr>
        """.format(long_verify_msg, long_status_msg)
    else:
        long_running_summary = ""
    
    statustable = """
    <table>
    <caption><h2>Test Result Table</h2><caption>
    <tr>
        <th>Distro</th>
        {0}
    </tr>
    <tr>
        <td>Install OMSAgent</td>
        {1}
    </tr>
    <tr>
        <td>Verify Data</td>
        {2}
    </tr>
    <tr>
        <td>Remove OMSAgent</td>
        {3}
    </tr>
    <tr>
        <td>Reinstall OMSAgent</td>
        {4}
    </tr>
    {5}
    <tr>
        <td>Result Link</td>
        {6}
    <tr>
    </table>
    """.format(diststh, install_oms_msg, verify_oms_msg, remove_oms_msg, reinstall_oms_msg, long_running_summary, resultsth)
    result_html_file.write(statustable)

    # Create final html & log file
    for vmname in vmnames:
        distname = vmname.split('-')[0]
        append_file(distname + "result.log", result_log_file)
        append_file(distname + "result.html", result_html_file)

    htmlend="""
    </body>
    </html>
    """
    result_html_file.write(htmlend)

if __name__ == '__main__':
    main()
