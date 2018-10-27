import json
import os
import os.path
import subprocess
import re
import sys
import time
import rstr

from collections import OrderedDict
from verify_e2e import check_e2e

from json2html import *

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

if len(sys.argv) > 1:
    vms_list = sys.argv[1:]
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
extension = parameters['extension'] #OmsAgentForLinux
publisher = parameters['publisher'] # Microsoft.EnterpriseCloud.Monitoring
key_vault = parameters['key vault']
subscription = str(json.loads(subprocess.check_output('az keyvault secret show --name susbscription-id --vault-name {0}'.format(key_vault), shell=True))["value"])
workspace_id = str(json.loads(subprocess.check_output('az keyvault secret show --name workspace-id --vault-name {0}'.format(key_vault), shell=True))["value"])
workspace_key = str(json.loads(subprocess.check_output('az keyvault secret show --name workspace-key --vault-name {0}'.format(key_vault), shell=True))["value"])
public_settings = { "workspaceId": workspace_id }
private_settings = { "workspaceKey": workspace_key }
nsg = "/subscriptions/"+ subscription + "/resourceGroups/" + nsg_resource_group + "/providers/Microsoft.Network/networkSecurityGroups/" + nsg_group

if os.system('az network nsg show --resource-group {0} --name {1}'.format(nsg_resource_group, nsg_group)) == 0:
    print "Network Security Group successfully validated"
else:
    print("""Please verify that the nsg or nsg resource group are valid and are in the right subscription.
If there is no Network Security Group, please create new one. NSG is a must to create a VM in this testing.""")
    exit()


resultlog = "finalresult.log"
resulthtml = "finalresult.html"
resultlogOpen = open(resultlog, 'a+')
resulthtmlOpen = open(resulthtml, 'a+')

# Common logic to save command itself
def write_log_command(outOpen, cmd):
    print(cmd)
    outOpen.write(cmd + '\n')
    outOpen.write('-' * 40)
    outOpen.write('\n')
    return

# Common logic to append a file to another
def append_file(filename, destFile):
    f = open(filename, 'r')
    destFile.write(f.read())
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

def copy_to_vm(dnsname, username, password, location):
    os.system("echo y | pscp -pw {} -r omsfiles/* {}@{}.{}.cloudapp.azure.com:/tmp/".format(password, username, dnsname.lower(), location))

def copy_from_vm(dnsname, username, password, location, filename):
    os.system("echo y | pscp -pw {} -r {}@{}.{}.cloudapp.azure.com:/tmp/{} .".format(password, username, dnsname.lower(), location, filename))

def run_command(resource_group, vmname, commandid, script):
    os.system('az vm run-command invoke -g {} -n {} --command-id {} --scripts "{}"'.format(resource_group, vmname, commandid, script))

def create_vm(resource_group, vmname, image, username, password, location, dnsname, vmsize, networksecuritygroup):
    os.system('az vm create -g {} -n {} --image {} --admin-username {} --admin-password {} --location {} --public-ip-address-dns-name {} --size {} --nsg {}'.format(resource_group, vmname, image, username, password, location, dnsname, vmsize, networksecuritygroup))

def add_extension(extension, publisher, vmname, resource_group, private_settings, public_settings):
    os.system('az vm extension set -n {} --publisher {} --vm-name {} --resource-group {} --protected-settings "{}" --settings "{}"'.format(extension, publisher, vmname, resource_group, private_settings, public_settings))

def remove_extension(extension, vmname, resource_group):
    os.system('az vm extension delete -n {} --vm-name {} --resource-group {}'.format(extension, vmname, resource_group))

def get_vm_resources(resource_group, vmname):
    vm_cli_out = json.loads(subprocess.check_output('az vm show -g {0} -n {1} --debug'.format(resource_group, vmname), shell=True))
    os_disk = vm_cli_out['storageProfile']['osDisk']['name']
    nic_name = vm_cli_out['networkProfile']['networkInterfaces'][0]['id'].split('/')[-1]
    ip_list = json.loads(subprocess.check_output('az vm list-ip-addresses -n {0} -g {1} --debug'.format(vmname, resource_group), shell=True))
    ip_name = ip_list[0]['virtualMachine']['network']['publicIpAddresses'][0]['name']
    return os_disk, nic_name, ip_name

def delete_vm(resource_group, vmname):
    os.system('az vm delete -g {} -n {} --yes'.format(resource_group, vmname))

def delete_vm_disk(resource_group, os_disk):
    os.system('az disk delete --resource-group {0} --name {1} --yes --debug'.format(resource_group, os_disk))

def delete_nic(resource_group, nic_name):
    os.system('az network nic delete --resource-group {0} --name {1} --no-wait --debug'.format(resource_group, nic_name))

def delete_ip(resource_group, ip_name):
    os.system('az network public-ip delete -resource-group {0} -name {1}'.format(resource_group, ip_name))


def create_vm_and_install_extensions(vmname, image, dnsname):
    print "\nCreate VM and Install Extension - {}: {} \n".format(vmname, image)
    create_vm(resource_group, vmname, image, username, password, location, dnsname, size, nsg)
    copy_to_vm(dnsname, username, password, location)
    remove_extension(extension, vmname, resource_group)
    run_command(resource_group, vmname, 'RunShellScript', 'python -u /tmp/oms_extension_run_script.py -preinstall')
    add_extension(extension, publisher, vmname, resource_group, private_settings, public_settings)
    run_command(resource_group, vmname, 'RunShellScript', 'python -u /tmp/oms_extension_run_script.py -postinstall')
    copy_from_vm(dnsname, username, password, location, 'omsresults.*')

def removing_extension(vmname, dnsname):
    print "\nRemove Extension: {} \n".format(vmname)
    remove_extension(extension, vmname, resource_group)
    run_command(resource_group, vmname, 'RunShellScript', 'python -u /tmp/oms_extension_run_script.py -status')
    copy_from_vm(dnsname, username, password, location, 'omsresults.*')

def reinstall_extension(vmname, dnsname):
    print "\n Reinstall Extension: {} \n".format(vmname)
    add_extension(extension, publisher, vmname, resource_group, private_settings, public_settings)
    run_command(resource_group, vmname, 'RunShellScript', 'python -u /tmp/oms_extension_run_script.py -status')
    copy_from_vm(dnsname, username, password, location, 'omsresults.*')

def remove_extension_and_delete_vm(vmname, dnsname, distname):
    print "\n Remove extension and Delete VM: {} \n".format(vmname)
    remove_extension(extension, vmname, resource_group)
    run_command(resource_group, vmname, 'RunShellScript', 'python -u /tmp/oms_extension_run_script.py -copyextlogs')
    copy_from_vm(dnsname, username, password, location, '{0}-extension.log'.format(distname))
    disk, nic, ip = get_vm_resources(resource_group, vmname)
    delete_vm(resource_group, vmname)
    delete_vm_disk(resource_group, disk)
    delete_nic(resource_group, nic)
    delete_ip(resource_group, ip)


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
resulthtmlOpen.write(htmlstart)

all_vms_install_message = ""

for distname, image in images.iteritems():
    uid = rstr.xeger(r'[0-9a-f]{8}')
    vmname = distname.lower() + '-' + uid
    vmnames.append(vmname)
    dnsname = vmname
    vmLog = distname.lower() + "result.log"
    htmlFile = distname.lower() + "result.html"
    logOpen = open(vmLog, 'a+')
    htmlOpen = open(htmlFile, 'a+')
    create_vm_and_install_extensions(vmname, image, dnsname)
    write_log_command(logOpen, 'Status After Creating VM and Adding OMS Extension')
    htmlOpen.write('<h1 id="{0}"> VM: {0} <h1>'.format(distname))
    htmlOpen.write("<h2> Install OMS Agent </h2>")
    append_file('omsresults.log', logOpen)
    append_file('omsresults.html', htmlOpen)
    logOpen.close()
    htmlOpen.close()
    status = open('omsresults.status', 'r').read()
    if status == "Agent Found":
        all_vms_install_message += """
                        <td><span style='background-color: #66ff99'>Install Success</span></td>"""
    elif status == "Onboarding Failed":
        all_vms_install_message += """
                        <td><span style='background-color: red; color: white'>Onboarding Failed</span></td>"""
    elif status == "Agent Not Found":
        all_vms_install_message += """
                        <td><span style='background-color: red; color: white'>Install Failed</span></td>"""
    

time.sleep(600)

all_vms_verify_message = ""

for vmname in vmnames:
    distname = vmname.split('-')[0]
    vmLog = distname + "result.log"
    htmlFile = distname + "result.html"
    logOpen = open(vmLog, 'a+')
    htmlOpen = open(htmlFile, 'a+')
    os.system('rm e2eresults.json')
    check_e2e(vmname)

    # write detailed table for vm
    htmlOpen.write("<h2> Verify Data from OMS workspace </h2>")
    write_log_command(logOpen, 'Status After Verifying Data')
    with open('e2eresults.json', 'r') as infile:
        data = json.load(infile)
    results = data[distname][0]
    logOpen.write(distname + ':\n' + json.dumps(results, indent=4, separators=(',', ': ')) + '\n')
    # prepend distro column to results row before generating the table
    data = [OrderedDict([('Distro', distname)] + results.items())]
    out = json2html.convert(data)
    htmlOpen.write(out)

    # write to summary table
    from verify_e2e import success_count
    if success_count == 6:
        all_vms_verify_message += """
                        <td><span style='background-color: #66ff99'>Verify Success</td>"""
    elif 0 < success_count < 6:
        from verify_e2e import success_sources, failed_sources
        all_vms_verify_message += """
                        <td><span style='background-color: #66ff99'>{0} Success</span> <br><br><span style='background-color: red; color: white'>{1} Failed</span></td>""".format(', '.join(success_sources), ', '.join(failed_sources))
    elif success_count == 0:
        all_vms_verify_message += """
                        <td><span style='background-color: red; color: white'>Verify Failed</span></td>"""

all_vms_delete_message = ""

for vmname in vmnames:
    distname = vmname.split('-')[0]
    vmLog = distname + "result.log"
    htmlFile = distname + "result.html"
    logOpen = open(vmLog, 'a+')
    htmlOpen = open(htmlFile, 'a+')
    dnsname = vmname
    removing_extension(vmname, dnsname)
    write_log_command(logOpen, 'Status After Removing OMS Extension')
    htmlOpen.write('<h2> Remove Extension <h2>'.format(vmname))
    append_file('omsresults.log', logOpen)
    append_file('omsresults.html', htmlOpen)
    logOpen.close()
    htmlOpen.close()
    status = open('omsresults.status', 'r').read()
    if status == "Agent Found":
        all_vms_delete_message += """
                        <td><span style="background-color: red; color: white">Remove Failed</span></td>"""
    elif status == "Onboarding Failed":
        all_vms_delete_message += """
                        <td><span style="background-color: red; color: white">Onboarding Failed</span></td>"""
    elif status == "Agent Not Found":
        all_vms_delete_message += """
                        <td><span style="background-color: #66ff99">Remove Success</span></td>"""


time.sleep(30)

all_vms_reinstall_message = ""

for vmname in vmnames:
    distname = vmname.split('-')[0]
    vmLog = distname + "result.log"
    htmlFile = distname + "result.html"
    logOpen = open(vmLog, 'a+')
    htmlOpen = open(htmlFile, 'a+')
    dnsname = vmname
    reinstall_extension(vmname, dnsname)
    write_log_command(logOpen, 'Status After Reinstall OMS Extension')
    htmlOpen.write('<h2> Reinstall Extension <h2>'.format(vmname))
    append_file('omsresults.log', logOpen)
    append_file('omsresults.html', htmlOpen)
    logOpen.close()
    htmlOpen.close()
    status = open('omsresults.status')
    if status == "Agent Found":
        all_vms_reinstall_message += """
                        <td><span style='background-color: #66ff99'>Reinstall Success</span></td>"""
    elif status == "Onboarding Failed":
        all_vms_reinstall_message += """
                        <td><span style='background-color: red; color: white'>Onboarding Failed</span></td>"""
    elif status == "Agent Not Found":
        all_vms_reinstall_message += """
                        <td><span style='background-color: red; color: white'>Reinstall Failed</span></td>"""

time.sleep(30)

for vmname in vmnames:
    distname = vmname.split('-')[0]
    vmLog = distname + "result.log"
    logOpen = open(vmLog, 'a+')
    dnsname = vmname
    remove_extension_and_delete_vm(vmname, dnsname, distname)
    append_file('{0}-extension.log'.format(distname), logOpen)
    logOpen.close()

diststh = ""
resultsth = ""
for vmname in vmnames:
    distname = vmname.split('-')[0]
    diststh += """
            <th>{0}</th>""".format(distname)
    resultsth += """
            <th><a href='#{0}'>{0} results</a></th>""".format(distname)

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
  <tr>
    <td>Result Link</td>
    {5}
  <tr>
</table>
""".format(diststh, all_vms_install_message, all_vms_verify_message, all_vms_remove_message, all_vms_reinstall_message, resultsth)
resulthtmlOpen.write(statustable)

# Create final html & log file
for vmname in vmnames:
    distname = vmname.split('-')[0]
    vmLog = distname + "result.log"
    htmlFile = distname + "result.html"
    append_file(vmLog, resultlogOpen)
    append_file(htmlFile, resulthtmlOpen)

htmlend="""
</body>
</html>
"""
resulthtmlOpen.write(htmlend)
resulthtmlOpen.close()
