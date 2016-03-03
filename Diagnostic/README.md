# Diagnostic Extension
Allow the owner of the Azure Virtual Machines to obtain diagnostic data for a Linux virtual machine.

Latest version is 2.3.4.

You can read the User Guide below for detail:
* [Use the Linux Diagnostic Extension to monitor the performance and diagnostic data of a Linux VM](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-linux-diagnostic-extension/)

Diagnostic Extension can:

* Collects and uploads Linux VM's system performance, diagnostic, and syslog data to user’s storage table.
* Enables user to customize the data metrics that will be collected and uploaded.
* Enables user to upload specified log files to designated storage table.


# User Guide

## 1. Configuration schema

### 1.1. Public configuration

Schema for the public configuration file looks like this:

* `perfCfg`: (required) A list of WQL query clauses, supported counters could be found in this [document](http://scx.codeplex.com/wikipage?title=xplatproviders&referringTitle=Documentation).
* `EnableSyslog`: (optional) Whether syslog data should be reported, currently only rsyslog is supported. Can choose from 'true' and 'false', default value is true.
* `fileCfg`: (optional) A list of files to be tracked, note this only works when EnableSyslog is set to true.
 
```json
{
  "perfCfg":[
    {
     "query":"SELECT UsedMemory,AvailableMemory FROM SCX_MemoryStatisticalInformation","table":"Memory"
    }
  ],
  "fileCfg":[
    {"file":"/var/log/a.log", "table":"aLog"},
    {"file":"/var/log/b.log", "table":"bLog"}
  ],
  "EnableSyslog":"true"
}
```


### 1.2. Protected configuration

Schema for the protected configuration file looks like this:


* `storageAccountName`: (required) the name of storage account
* `storageAccountKey`: (required) the access key of storage account

```json
{
  "storageAccountName": "<storage-account-name>",
  "storageAccountKey": "<storage-account-key>"
}
```

**NOTE:**

The storage account is used for storing the diagnostic montioring data, the data would be sent to the [Table storage](https://azure.microsoft.com/en-us/documentation/articles/storage-dotnet-how-to-use-tables/) of that account.

Please note that premium storage account could not be used since it [does not support Table storage](https://azure.microsoft.com/en-us/documentation/articles/storage-premium-storage-preview-portal/).

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.

**NOTE:**

Creating VM in Azure has two deployment model: Classic and [Resource Manager][arm-overview].
In diffrent models, the deploying commands have different syntaxes. Please select the right
one in section 2.1 and 2.2 below.
 
### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying Diagnostic Extension, you should configure your `public.json` and `protected.json`
(in section 1.1 and 1.2 above).

#### 2.1.1 Classic
The Classic mode is also called Azure Service Management mode. You can change to it by running:
```
$ azure config mode asm
```

You can deploying Diagnostic Extension by running:
```
$ azure vm extension set <vm-name> LinuxDiagnostic Microsoft.OSTCExtensions '2.*' -c public.json -e protected.json
```

In the command above, you can change version with `'*'` to use latest version available, or `'2.*'` to get newest version that does not introduce non-breaking schema changes.


#### 2.1.2 Resource Manager
You can change to Azure Resource Manager mode by running:
```
$ azure config mode arm
```

You can deploying Diagnostic Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> LinuxDiagnostic Microsoft.OSTCExtensions <version> -c public.json  -e protected.json
```

### 2.2. Using [**Azure Powershell**][azure-powershell]

#### 2.2.1 Classic

You can login to your Azure account (Azure Service Management mode) by running:

```powershell
Add-AzureAccount
```

You can deploying Diagnostic Extension by running:

```powershell
$VmName = '<vm-name>'
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$ExtensionName = 'LinuxDiagnostic'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '<version>'

$PublicConf = '{
  "perfCfg":[
    {
     "query":"SELECT UsedMemory,AvailableMemory FROM SCX_MemoryStatisticalInformation","table":"Memory"
    }
  ],
  "fileCfg":[
    {"file":"/var/log/a.log", "table":"aLog"},
    {"file":"/var/log/b.log", "table":"bLog"}
  ],
  "EnableSyslog":"true"
}'

$PrivateConf = '{
    "storageAccountName": "<storage-account-name>",
    "storageAccountKey": "<storage-account-key>"
}'

Set-AzureVMExtension -ExtensionName $ExtensionName -VM $vm `
  -Publisher $Publisher -Version $Version `
  -PrivateConfiguration $PrivateConf -PublicConfiguration $PublicConf |
  Update-AzureVM
```

#### 2.2.2 Resource Manager

You can login to your Azure account (Azure Resource Manager mode) by running:

```powershell
Login-AzureRmAccount
```

Click [**HERE**](https://azure.microsoft.com/en-us/documentation/articles/powershell-azure-resource-manager/) to learn more about how to use Azure Powershell with Azure Resource Manager.

You can deploying LinuxDiagnostic Extension by running:

```powershell
$RGName = '<resource-group-name>'
$VmName = '<vm-name>'
$Location = '<location>'

$ExtensionName = 'LinuxDiagnostic'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '<version>'

$PublicConf = '{
  "perfCfg":[
    {
     "query":"SELECT UsedMemory,AvailableMemory FROM SCX_MemoryStatisticalInformation","table":"Memory"
    }
  ],
  "fileCfg":[
    {"file":"/var/log/a.log", "table":"aLog"},
    {"file":"/var/log/b.log", "table":"bLog"}
  ],
  "EnableSyslog":"true"
}'

$PrivateConf = '{
    "storageAccountName": "<storage-account-name>",
    "storageAccountKey": "<storage-account-key>"
}'

Set-AzureRmVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher `
  -ExtensionType $ExtensionName -TypeHandlerVersion $Version `
  -Settingstring $PublicConf -ProtectedSettingString $PrivateConf
```

### 2.3. Using [**ARM Template**][arm-template]

```json
{
  "type": "Microsoft.Compute/virtualMachines/extensions",
  "name": "<extension-deployment-name>",
  "apiVersion": "<api-version>",
  "location": "<location>",
  "dependsOn": [
    "[concat('Microsoft.Compute/virtualMachines/', <vmName>)]"
  ],
  "properties": {
    "publisher": "Microsoft.OSTCExtensions",
    "type": "LinuxDiagnostic",
    "typeHandlerVersion": "2.2",
    "settings": {
       "perfCfg":[
          {
            "query":"SELECT UsedMemory,AvailableMemory FROM SCX_MemoryStatisticalInformation","table":"Memory"
          }
        ]
    },
    "protectedSettings": {
      "storageAccountName": "<storage-account-name>",
      "storageAccountKey": "<storage-account-key>"
    }
  }
}
```

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).


## Supported Linux Distributions
- Ubuntu 12.04 and higher
- CentOS 6.5 and higher
- Oracle Linux 6.4.0.0.0 and higher
- openSUSE 13.1 and higher
- SUSE Linux Enterprise Server 12 and higher (SLES 11 SP4 support will be added back in the next release. The source code comment should have been updated)

## Debug

* The status of the extension is reported back to Azure so that user can see the status on Azure Portal
* The operation log of the extension is `/var/log/azure/Microsoft.OSTCExtensions.LinuxDiagnostic/<version>/` directory.

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
