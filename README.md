# Linux extensions for Microsoft Azure IaaS

This project provides the source code of Linux extensions for Microsoft Azure IaaS.

VM Extensions are injected components authored by Microsoft and Partners into Linux VM (IaaS) to enable software and configuration automation.

# Extension List

| Name | Lastest Version | Description |
|:---|:---|:---|
| [Custom Script](https://github.com/Azure/azure-linux-extensions/tree/master/CustomScript) | 1.4 | Allow the owner of the Azure Virtual Machines to run customized scripts in the VM |
| [DSC](https://github.com/Azure/azure-linux-extensions/tree/master/DSC) | 1.0 | Allow the owner of the Azure Virtual Machines to configure the VM using Windows PowerShell Desired State Configuration (DSC) for Linux |
| [OS Patching](https://github.com/Azure/azure-linux-extensions/tree/master/OSPatching) | 2.0 | Allow the owner of the Azure VM to configure the Linux VM patching schedule cycle |
| [VM Access](https://github.com/Azure/azure-linux-extensions/tree/master/VMAccess) | 1.3 | Provide several ways to allow owner of the VM to get the SSH access back |

# Contributing Guide

Please refer to [**HERE**](./docs/contribution-guide.md).

# Known Issues
1. When you run the PowerShell command "Set-AzureVMExtension" on Linux VM, you may hit following error: "Provision Guest Agent must be enabled on the VM object before setting IaaS VM Access Extension". 

  * Root Cause: When you create the Linux VM via portal, the value of provision guest agent on the VM is not always set to "True". If your VM is created using PowerShell or using the Azure new portal, you will not see this issue.

  * Resolution: Add the following PowerShell command to set the ProvisionGuestAgent to "True".
  ```powershell
  $vm = Get-AzureVM -ServiceName 'MyServiceName' -Name 'MyVMName'
  $vm.GetInstance().ProvisionGuestAgent = $true
  ```
