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
* `ResourceZipFileUri`: (optional, string) the uri of the custom resource ZIP file
* `ResourceName`: (optional, string) the name of the custom resource module
* `Mode`: (optional, string) the functional mode, valid values: Push, Pull, Install, Remove. If not specified, it's considered as Pull mode.

### 1.2 Protected configuration

Here're all the supported protected configuration parameters:

* `StorageAccountName`: (optional, string) the name of the storage account that contains the file
* `StorageAccountKey`: (optional, string) the key of the storage account that contains the file
* `ContainerName`: (optional, string) the name of the container that contains the file
* `MofFileName`: (optional, string) the name of the MOF file in the Azure Storage Account
* `ResourceZipFileName`: (optional, string) the name of the custom resource ZIP file in the Azure Storage Account, the format should be "name_version.zip".

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure PowerShell and ARM template.

### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying DSCForLinux Extension, you should configure your `public.json` and `protected.json`, according to the different scenarios in section 3.

#### 2.1.1. Classic
The Classic mode is also called Azure Service Management mode. You can switch to it by running:
```
$ azure config mode asm
```

You can deploy DSCForLinux Extension by running:
```
$ azure vm extension set <vm-name> DSCForLinux Microsoft.OSTCExtensions <version> \
--private-config-path protected.json --public-config-path public.json
```

To learn the latest extension version available, run:
```
$ azure vm extension list
```

#### 2.1.2. Resource Manager
You can switch to Azure Resource Manager mode by running:
```
$ azure config mode arm
```

You can deploy DSCForLinux Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> \
DSCForLinux Microsoft.OSTCExtensions <version> \
--private-config-path protected.json --public-config-path public.json
```

> **NOTE:** In ARM mode, `azure vm extension list` is not available for now.

### 2.2. Using [**Azure PowerShell**][azure-powershell]

#### 2.2.1 Classic
You can switch to Azure Service Management mode by running:
```powershell
Switch-AzureMode -Name AzureServiceManagement
```
And deploy DSCForLinux Extension by running:
```powershell
$vmname = '<vm-name>'
$vm = Get-AzureVM -ServiceName $vmname -Name $vmname

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = '<version>'

# You need to change the content of the $privateConfig and $publicConfig 
# according to different scenarios in section 3
$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<mof-file-name>"
}'

$publicConfig = '{
  "Mode": "Push"
}'

Set-AzureVMExtension -ExtensionName $extensionName -VM $vm -Publisher $publisher `
  -Version $version -PrivateConfiguration $privateConfig `
  -PublicConfiguration $publicConfig | Update-AzureVM
```

#### 2.2.2.Resource Manager
You can change to Azure Resource Manager mode by running:
```powershell
Switch-AzureMode -Name AzureResourceManager
```
You can deploy DSCForLinux Extension by running:
```powershell
$rgName = '<resource-group-name>'
$vmName = '<vm-name>'
$location = '<location>'

$extensionName = 'DSCForLinux'
$publisher = 'Microsoft.OSTCExtensions'
$version = <version>

# You need to change the content of the $privateConfig and $publicConfig 
# according to different scenarios in section 3
$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<mof-file-name>"
}'

$publicConfig = '{
  "Mode": "Push"
}'

Set-AzureVMExtension -ResourceGroupName $rgName -VMName $vmName -Location $location `
  -Name $extensionName -Publisher $publisher -ExtensionType $extensionName `
  -TypeHandlerVersion $version -SettingString $publicConfig -ProtectedSettingString $privateConfig
```

For more details about Set-AzureVMExtension syntax in ARM mode, please visit [Set-AzureVMExtension][Set-AzureVMExtension-ARM].

### 2.3. Using [**ARM Template**][arm-template]

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).

## 3. Scenarios

### 3.1 Apply a MOF configuration file (in Azure Storage Account) to the VM

protected.json
```json
{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<mof-file-name>"
}
```

powershell format
```powershell
$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<mof-file-name>"
}'
```

### 3.2. Apply a MOF configuration file (in public storage) to the VM

public.json
```json
{
  "MofFileUri": "<mof-file-uri>"
}
```

powershell format
```powershell
$publicConfig = '{
  "MofFileUri": "<mof-file-uri>"
}'
```

### 3.3. Apply a meta MOF configuration file (in Azure Storage Account) to the VM

protected.json
```json
{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<meta-mof-file-name>"
}
```

public.json
```json
{
  "Mode": "Pull"
}
```

powershell format
```powershell
$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "MofFileName": "<meta-mof-file-name>"
}'

$publicConfig = '{
  "Mode": "Pull"
}'
```

### 3.4. Apply a meta MOF configuration file (in public storage) to the VM
public.json
```json
{
  "MofFileUri": "<meta-mof-file-uri>",
  "Mode": "Pull"
}
```
powershell format
```powershell
$publicConfig = '{
  "MofFileUri": "<meta-mof-file-uri>",
  "Mode": "Pull"
}'
```

### 3.5. Install a custom resource module (ZIP file in Azure Storage Account) to the VM
protected.json
```json
{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "ResourceZipFileName": "<resource-zip-file-name>"
}
```
public.json
```json
{
  "Mode": "Install"
}
```

powershell format
```powershell
$privateConfig = '{
  "StorageAccountName": "<storage-account-name>",
  "StorageAccountKey": "<storage-account-key>",
  "ContainerName": "<container-name>",
  "ResourceZipFileName": "<resource-zip-file-name>"
}'

$publicConfig = '{
  "Mode": "Install"
}'
```

### 3.6. Install a custom resource module (ZIP file in public storage) to the VM
public.json
```json
{
  "ResourceZipFileUri": "<resource-zip-file-uri>",
  "Mode": "Install"
}
```
powershell format
```powershell
$publicConfig = '{
  "ResourceZipFileUri": "<resource-zip-file-uri>",
  "Mode": "Install"
}'
```

### 3.7. Remove a custom resource module from the VM
public.json
```json
{
  "ResourceName": "<resource-name>",
  "Mode": "Remove"
}
```
powershell format
```powershell
$publicConfig = '{
  "ResourceName": "<resource-name>",
  "Mode": "Remove"
}'
```

## 4. Supported Linux Distributions
- Ubuntu 12.04 LTS, 14.04 LTS
- CentOS 6.5 and higher
- Oracle Linux 6.4 and higher
- openSUSE 13.1 and higher
- SUSE Linux Enterprise Server 11 SP3 and higher

## 5. Debug
* The status of the extension is reported back to Azure so that user can see the status on Azure Portal
* The operation log of the extension is `/var/log/azure/<extension-name>/<version>/extension.log` file.

## 6. Known issue
* To distribute MOF configurations to the Linux VM with Pull Servers, you need to make sure the cron service is running in the VM.

## Changelog
### v1.0 Sep. 24, 2015
Initial version

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
[Set-AzureVMExtension-ARM]: https://msdn.microsoft.com/en-us/library/mt163544.aspx
