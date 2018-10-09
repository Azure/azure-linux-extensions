
images = "<copy the ones you want to create and run from the list below>"
# Optional: The key values will be your VM Names. You can edit the key values to change the name of the VM
#       { 'omsUbuntu14': 'Canonical:UbuntuServer:14.04.5-LTS:14.04.201808180' }
#         'omsUbuntu16': 'Canonical:UbuntuServer:16.04-LTS:latest',
#         'omsUbuntu18': 'Canonical:UbuntuServer:18.04-LTS:latest',
#         'omsDebian8': 'credativ:Debian:8:latest',
#         'omsDebian9': 'credativ:Debian:9:latest',
#         'omsRHEL69': 'RedHat:RHEL:6.9:latest',
#         'omsRHEL73': 'RedHat:RHEL:7.3:latest',
#         'omsCentOS69': 'OpenLogic:CentOS:6.9:latest',
#         'omsCentOS75': 'OpenLogic:CentOS:7.5:latest',
#         'omsOracle69': 'Oracle:Oracle-Linux:6.9:latest',
#         'omsOracle75': 'Oracle:Oracle-Linux:7.5:latest',
#         'omsSUSE12': 'SUSE:SLES:12-SP2:latest'}

##Please replace the below variables with your own
username = "username"
#Password must have 3 of the following: 1 lower case character, 1 upper case character, 1 number, and 1 special character that is not '\' or '-' & The value must be between 12 and 72 characters long.
#ex: omsPLMokn098
password = "password"
location = "location" #ex: eastus2euap
rGroup = "resourcegroup"
#networkSecurityGroups are different for each region for every subscription. Please check the nsgs available for the location and your subscription and add the right one.
#ex: "/subscriptions/<subscription-id>/resourceGroups/eastus2euapRG/providers/Microsoft.Network/networkSecurityGroups/eastus2euapnsg". There are other ways to declare an nsg but this will make sure you are on the right one.
nsg = "/subscriptions/<subscription-id>/resourceGroups/<nsg-resource-group>/providers/Microsoft.Network/networkSecurityGroups/<nsg-group>"
extension = "OmsAgentForLinux"
publisher = "Microsoft.EnterpriseCloud.Monitoring"
size = "Standard_B1ms"
public_settings = "<private-settings>" #{ "workspaceId": "<workspace-id>" }
private_settings = "<public_settings>" #{ "workspaceKey": "<workspace-key>" }