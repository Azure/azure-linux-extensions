# OmsAgent Extension

[See the latest version and extension-bundle mapping.](https://docs.microsoft.com/en-us/azure/virtual-machines/extensions/oms-linux#agent-and-vm-extension-version)

You can read the User Guide below.
* [Learn more: Azure Virtual Machine Extensions](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-extensions-features/)

OmsAgent Extension can:
* Install the omsagent
* Onboard to a OMS workspace

# User Guide

## 1. Configuration schema

### 1.1. Public configuration

Schema for the public configuration file looks like this:

* `workspaceId`: (required, string) the OMS workspace id to onboard to
* `stopOnMultipleConnections`: (optional, true/false) warn and stop onboarding if the machine already has a workspace connection; defaults to false
 
```json
{
  "workspaceId": "<workspace-id (guid)>",
  "stopOnMultipleConnections": true/false
}
```

### 1.2. Protected configuration

Schema for the protected configuration file looks like this:

* `workspaceKey`: (required, string) the primary/secondary shared key of the workspace
* `proxy`: (optional, string) the proxy connection string - of the form \[user:pass@\]host\[:port\]
* `vmResourceId`: (optional, string) the full azure resource id of the vm - of the form /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Compute/virtualMachines/{vmName} for Resource Manager VMs and of the form /subscriptions/{subscriptionId}/resourceGroups/{vmName}/providers/Microsoft.ClassicCompute/virtualMachines/{vmName} for Classic VMs

```json
{
  "workspaceKey": "<workspace-key>",
  "proxy": "<proxy-string>",
  "vmResourceId": "<vm-resource-id>"
}
```

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.


 
### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying OmsAgent Extension, you should configure your `public.json` and `protected.json`
(in section 1.1 and 1.2 above).

#### 2.1.1 Resource Manager

You can deploy the OmsAgent Extension by running:
```
az vm extension set \
  --resource-group myResourceGroup \
  --vm-name myVM \
  --name OmsAgentForLinux \
  --publisher Microsoft.EnterpriseCloud.Monitoring \
  --version <version> --protected-settings '{"workspaceKey": "omskey"}' \
  --settings '{"workspaceId": "omsid"}'

```

#### 2.1.2 Classic
Classic mode is used to managed legacy resources created outside of Resource Manager, and requires the [classic cli][azure-cli-classic] to manage via the command line.
You need to enable Classic Mode (also called Azure Service Management mode) in the cli by running:
```
azure config mode asm
```

You can deploy the OmsAgent Extension by running:
```
azure vm extension set <vm-name> \
OmsAgentForLinux Microsoft.EnterpriseCloud.Monitoring <version> \
--public-config-path public.json  \
--private-config-path protected.json
```

In the command above, you can change version with `'*'` to use latest
version available, or `'1.*'` to get newest version that does not introduce non-
breaking schema changes. To learn the latest version available, run:
```
azure vm extension list
```

### 2.2. Using [**Azure Powershell**][azure-powershell]

#### 2.2.1 Resource Manager

You can login to your Azure account (Azure Resource Manager mode) by running:

```powershell
Login-AzureRmAccount
```

Click [**HERE**](https://azure.microsoft.com/en-us/documentation/articles/powershell-azure-resource-manager/) to learn more about how to use Azure Powershell with Azure Resource Manager.

You can deploy the OmsAgent Extension by running:

```powershell
$RGName = '<resource-group-name>'
$VmName = '<vm-name>'
$Location = '<location>'

$ExtensionName = 'OmsAgentForLinux'
$Publisher = 'Microsoft.EnterpriseCloud.Monitoring'
$Version = '<version>'

$PublicConf = '{
    "workspaceId": "<workspace id>",
    "stopOnMultipleConnections": true/false
}'
$PrivateConf = '{
    "workspaceKey": "<workspace key>",
    "proxy": "<proxy string>",
    "vmResourceId": "<vm resource id>"
}'

Set-AzureRmVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher `
  -ExtensionType $ExtensionName -TypeHandlerVersion $Version `
  -Settingstring $PublicConf -ProtectedSettingString $PrivateConf
```

#### 2.2.2 Classic

You can login to your Azure account (Azure Service Management mode) by running:

```powershell
Add-AzureAccount
```

You can deploy the OmsAgent Extension by running:

```powershell
$VmName = '<vm-name>'
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$ExtensionName = 'OmsAgentForLinux'
$Publisher = 'Microsoft.EnterpriseCloud.Monitoring'
$Version = '<version>'

$PublicConf = '{
    "workspaceId": "<workspace id>",
    "stopOnMultipleConnections": true/false
}'
$PrivateConf = '{
    "workspaceKey": "<workspace key>",
    "proxy": "<proxy string>",
    "vmResourceId": "<vm resource id>"
}'

Set-AzureVMExtension -ExtensionName $ExtensionName -VM $vm `
  -Publisher $Publisher -Version $Version `
  -PrivateConfiguration $PrivateConf -PublicConfiguration $PublicConf |
  Update-AzureVM
```


### 2.3. Using [**ARM Template**][arm-template]
```json
{
  "type": "Microsoft.Compute/virtualMachines/extensions",
  "name": "<extension-deployment-name>",
  "apiVersion": "<api-version>",
  "location": "<location>",
  "dependsOn": [
    "[concat('Microsoft.Compute/virtualMachines/', <vm-name>)]"
  ],
  "properties": {
    "publisher": "Microsoft.EnterpriseCloud.Monitoring",
    "type": "OmsAgentForLinux",
    "typeHandlerVersion": "1.4",
    "settings": {
      "workspaceId": "<workspace id>",
      "stopOnMultipleConnections": true/false
    },
    "protectedSettings": {
      "workspaceKey": "<workspace key>",
      "proxy": "<proxy string>",
      "vmResourceId": "<vm resource id>"
    }
  }
}
```

## 3. Scenarios

### 3.1 Onboard to OMS workspace
```json
{
  "workspaceId": "MyWorkspaceId",
  "stopOnMultipleConnections": true
}
```
```json
{
  "workspaceKey": "MyWorkspaceKey",
  "proxy": "proxyuser:proxypassword@proxyserver:8080",
  "vmResourceId": "/subscriptions/c90fcea1-7cd5-4255-9e2e-25d627a2a259/resourceGroups/RGName/providers/Microsoft.Compute/virtualMachines/VMName"
}
```

## [Supported Linux Distributions](https://docs.microsoft.com/en-us/azure/azure-monitor/platform/log-analytics-agent#supported-linux-operating-systems)

## Troubleshooting

* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* All the execution output and errors generated by the extension are logged into
the following directories -
`/var/lib/waagent/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux-<version>/packages/`, `/opt/microsoft/omsagent/bin`
and the tail of the output is logged into the log directory specified
in HandlerEnvironment.json and reported back to Azure
* The operation log of the extension is `/var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/<version>/extension.log` file.

### Common error codes and their meanings

| Error Code | Meaning | Possible Action |
| :---: | --- | --- |
| 10 | VM is already connected to an OMS workspace | To connect the VM to the workspace specified in the extension schema, set stopOnMultipleConnections to false in public settings or remove this property. This VM gets billed once for each workspace it is connected to. |
| 11 | Invalid config provided to the extension | Follow the preceding examples to set all property values necessary for deployment. |
| 12 | The dpkg package manager is locked | Make sure all dpkg update operations on the machine have finished and retry. |
| 20 | Enable called prematurely | [Update the Azure Linux Agent](https://docs.microsoft.com/en-us/azure/virtual-machines/linux/update-agent) to the latest available version. |
| 40-44 | Issue with the Automatic Management scenario | Please contact support with the details from the /var/log/azure/Microsoft.EnterpriseCloud.Monitoring.OmsAgentForLinux/\<version\>/extension.log |
| 51 | This extension is not supported on the VM's operation system | |
| 52 | The extension failed due to a missing dependency | |
| 53 | The extension failed due to missing or wrong configuration parameters | |
| 55 | Cannot connect to the Microsoft Operations Management Suite service | Check that the system either has Internet access, or that a valid HTTP proxy has been provided. Additionally, check the correctness of the workspace ID. |

Additional error codes and troubleshooting information can be found on the [OMS-Agent-for-Linux Troubleshooting Guide](https://github.com/Microsoft/OMS-Agent-for-Linux/blob/master/docs/Troubleshooting.md#).


[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli-classic]: https://docs.microsoft.com/en-us/cli/azure/install-classic-cli
[azure-cli]: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
