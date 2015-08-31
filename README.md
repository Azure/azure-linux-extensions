# Linux extensions for Microsoft Azure IaaS

This project provides the source code of Linux extensions for Microsoft Azure IaaS.

VM Extensions are injected components authored by Microsoft and Partners into Linux VM (IaaS) to enable software and configuration automation.

# Extension List

| Name | Lastest Version | Description |
|:---|:---|:---|
| [Custom Script](https://github.com/Azure/azure-linux-extensions/tree/master/CustomScript) | 1.3 | Allow the owner of the Azure Virtual Machines to run customized scripts in the VM |
| [DSC](https://github.com/Azure/azure-linux-extensions/tree/master/DSC) | 1.0 | Allow the owner of the Azure Virtual Machines to configure the VM using Windows PowerShell Desired State Configuration (DSC) for Linux |
| [OS Patching](https://github.com/Azure/azure-linux-extensions/tree/master/OSPatching) | 2.0 | Allow the owner of the Azure VM to configure the Linux VM patching schedule cycle |
| [VM Access](https://github.com/Azure/azure-linux-extensions/tree/master/VMAccess) | 1.3 | Provide several ways to allow owner of the VM to get the SSH access back |

# Contributing guide
3rd party partners are welcomed to contribute the Linux extensions. Before you make a contribution, you should read the following guide.

## 1. HandlerManifest.json
The extensions are installed, enabled, disabled, updated and uninstalled by [Azure Linux Agent](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-linux-agent-user-guide/).

You can see these common commands in `HandlerManifest.json` and take [here](https://github.com/Azure/azure-linux-extensions/blob/master/CustomScript/HandlerManifest.json) as an example.

The most important commands:
* The `install` command is executed only when the extension is deployed the VM for the first time.
* The `enable` command will enable your configurations (in section 2).

## 2. Configuraions
The configurations include two parts: public configuration and protected configuration.

They are in JSON format and defined in every specific configuration.

## How to test
1. Install the extension in your virtual machine on Azure.
2. `cd /var/lib/waagent` and you can see your extension path.
3. Fix the bug which you found, and test your code change just by re-enabling the extension.
4. Feel free to create your pull request.

# Debug
1. The status of the extension is reported back to Azure, and you can see the status on Azure Portal.
2. You can check `/var/log/waagent.log` to verify if the extension is enabled successfully.
3. The operation log of the extension is `/var/log/azure/<extension-name>/<version>/extension.log` file.

# Known Issues
1. When you run the PowerShell command "Set-AzureVMExtension" on Linux VM, you may hit following error: "Provision Guest Agent must be enabled on the VM object before setting IaaS VM Access Extension". This does not happen if you are using the new portal.

  * Root Cause: When you create the image via portal, the value of guest agent on the VM is not always set to "True". If your VM is created using PowerShell, you will not see this issue.

  * Resolution: Add the following PowerShell command to set the ProvisionGuestAgent to "True";
  ```powershell
  $vm = Get-AzureVM -ServiceName 'MyServiceName' -Name 'MyVMName'
  $vm.GetInstance().ProvisionGuestAgent = $true
  ```
