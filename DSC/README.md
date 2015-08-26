# DSCForLinux Extension
Allow the owner of the Azure Virtual Machines to configure the VM using Windows PowerShell Desired State Configuration (DSC) for Linux.

Latest version is 1.0.

You can read the User Guide below.
* [Learn more: Azure Virtual Machine Extensions](https://msdn.microsoft.com/en-us/library/azure/dn606311.aspx)

About how to create MOF document, please refer to below documents.
* [Get started with Windows PowerShell Desired State Configuration for Linux](https://technet.microsoft.com/en-us/library/mt126211.aspx)
* [Built-In Windows PowerShell Desired State Configuration Resources for Linux](https://technet.microsoft.com/en-us/library/mt126209.aspx)

DSCForLinux Extension can:
* Push MOF configurations to the Linux VM (Push Mode)
* Distribute MOF configurations to the Linux VM with Pull Servers (Pull Mode)
* Install custom DSC modules to the Linux VM (Install Mode)
* Remove custom DSC modules to the Linux VM (Remove Mode)

# User Guide

## 1. Configuration schema

### 1.1. Public configuration

Here're all the supported public configuration parameters:

* `MofFileUri`: (optional, string) the uri of the public MOF file
* `ResourceZipFileUrl`: (optional, string) the uri of the custom resource ZIP file
* `ResourceName`: (optional, string) the name of the custom resource module
* `Mode`: (optional, string) the functional mode, valid values: Push, Pull, Install, Remove. If not specified, it's considered as Pull mode.

### 1.2 Private configuration

Here're all the supported private configuration parameters:

* `StorageAccountName`: (optional, string) the name of the storage account that contains the file
* `StorageAccountKey`: (optional, string) the key of the storage account that contains the file
* `ContainerName`: (optional, string) the name of the container that contains the file
* `MofFileName`: (optional, string) the name of the MOF file in the Azure Storage Account
* `ResourceZipFileName`: (optional, string) the name of the custom resource ZIP file in the Azure Storage Account, the format should be "name_version.zip".

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI and Azure PowerShell.

### 2.1. Apply a MOF configuration file (in Azure Storage Account) to the VM

#### 2.1.1. Using [**Azure CLI**][azure-cli]
Create the private configuration json file (private.json) with following content
```json
{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<mof-file-name>"
}
```

Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> --private-config-path private.json
```

#### 2.1.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<mof-file-name>"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PrivateConfiguration $privateConfig | Update-AzureVM
```

### 2.2. Apply a public MOF configuration file to the VM

#### 2.2.1. Using [**Azure CLI**][azure-cli]
Create the public configuration json file (public.json) with following content
```json
{
  "MofFileUri": "<mof-file-uri>"
}
```

Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> --public-config-path public.json
```

#### 2.2.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$publicConfig = '{
  "MofFileUri": "<mof-file-uri>"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PublicConfiguration $publicConfig | Update-AzureVM
```

### 2.3. Apply a meta MOF configuration file (in Azure Storage Account) to the VM

#### 2.3.1. Using [**Azure CLI**][azure-cli]
Create the private configuration json file (private.json) with following content
```json
{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<meta-mof-file-name>"
}
```
Create the public configuration json file (public.json) with following content
```json
{
  "Mode": "Pull"
}
```
Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> `
  --private-config-path private.json --public-config-path public.json
```

#### 2.3.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<meta-mof-file-name>"
}'

$publicConfig = '{
  "Mode": "Pull"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PrivateConfiguration $privateConfig -PublicConfiguration $publicConfig `
  | Update-AzureVM
```

### 2.4. Apply a public meta MOF configuration file to the VM

#### 2.4.1. Using [**Azure CLI**][azure-cli]
Create the public configuration json file (public.json) with following content
```json
{
  "MofFileUri": "<meta-mof-file-uri>",
  "Mode": "Pull"
}
```

Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> --public-config-path public.json
```

#### 2.4.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$publicConfig = '{
  "MofFileUri": "<mof-file-uri>",
  "Mode": "Pull"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PublicConfiguration $publicConfig | Update-AzureVM
```

### 2.5. Install a custom resource module (ZIP file in Azure Storage Account) to the VM

#### 2.5.1. Using [**Azure CLI**][azure-cli]
Create the private configuration json file (private.json) with following content
```json
{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "ResourceZipFileName": "<resource-zip-file-name>"
}
```
Create the public configuration json file (public.json) with following content
```json
{
  "Mode": "Install"
}
```
Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> `
  --private-config-path private.json --public-config-path public.json
```

#### 2.5.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "ResourceZipFileName": "<resource-zip-file-name>"
}'

$publicConfig = '{
  "Mode": "Install"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PrivateConfiguration $privateConfig -PublicConfiguration $publicConfig `
  | Update-AzureVM
```

### 2.6. Install a custom resource module (public ZIP file) to the VM

#### 2.6.1. Using [**Azure CLI**][azure-cli]
Create the public configuration json file (public.json) with following content
```json
{
  "ResourceZipFileUri": "<resource-zip-file-uri>",
  "Mode": "Install"
}
```

Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> --public-config-path public.json
```

#### 2.6.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$publicConfig = '{
  "ResourceZipFileUri": "<resource-zip-file-uri>",
  "Mode": "Install"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PublicConfiguration $publicConfig | Update-AzureVM
```

### 2.7. Remove a custom resource module from the VM

#### 2.7.1. Using [**Azure CLI**][azure-cli]
Create the public configuration json file (public.json) with following content
```json
{
  "ResourceName": "<resource-name>",
  "Mode": "Remove"
}
```

Enable the extension by running:
```
azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> --public-config-path public.json
```

#### 2.7.2. Using [**Azure PowerShell**][azure-powershell]
Enable the extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

$publicConfig = '{
  "ResourceName": "<resource-name>",
  "Mode": "Remove"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PublicConfiguration $publicConfig | Update-AzureVM
```

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
[Set-AzureVMExtension-ARM]: https://msdn.microsoft.com/en-us/library/mt163544.aspx
