# Diagnostic Extension
Allow the owner of the Azure Virtual Machines to obtain diagnostic data for a Linux virtual machine.

Latest version is 2.3.9021.

You can read the User Guide below for detail:
* [Use the Linux Diagnostic Extension to monitor the performance and diagnostic data of a Linux VM](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-linux-diagnostic-extension/)

Diagnostic Extension can:

* Collects and uploads Linux VM's system performance, diagnostic, and syslog data to user’s storage table.
* Enables user to customize the data metrics that will be collected and uploaded.
* Enables user to upload specified log files to designated storage table.


## Important Notice

***The new Azure Portal's VM Diagnostic extension status and performance graphs will not work***
if the Linux Azure Diagnostic extension is configured using one of the methods described in this
document (that is, using either Azure Powershell or Azure XPLAT CLI with the JSON configs below).
The Azure Portal's VM Diagnostic extension status and the performance graphs requires that this
extension be enabled only through the Azure Portal.



# User Guide

## 1. Configuration schema

### 1.1. Public configuration

Schema for the public configuration file looks like this:

* `perfCfg`: (optional) A list of WQL query clauses, supported counters could be found in this [document](http://scx.codeplex.com/wikipage?title=xplatproviders&referringTitle=Documentation). If no perfCfg entry is specified, then memory, CPU, and disk perf counters are added by default. If no perf counters should be collected, give an empty array ([]) as the value for this key.
* `enableSyslog`: (optional) Whether syslog data should be reported, currently only rsyslog is supported. Can choose from 'true' and 'false', default value is true.
* `fileCfg`: (optional) A list of files to be tracked, note this only works when enableSyslog is set to true.
* `mdsdHttpProxy`: (optional) http proxy configuration for mdsd. Format: "http://proxy_host:proxy_port". "http:" part is optional. DO NOT specify username and password here!
 
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
  "enableSyslog":"true",
  "mdsdHttpProxy":"http://your_proxy_host:3128"
}
```


### 1.2. Protected configuration

Schema for the protected configuration file looks like this:


* `storageAccountName`: (required) the name of storage account
* `storageAccountSasToken` or `storageAccountKey`: (required) a valid account SAS token for the storage acocunt or the access key of storage account. Only one of these two should be given. Note that `storageAccountKey` may be deprecated in some future. For the `storageAccountSasToken` requirements, please see below.
* `mdsdHttpProxy`: (optional) http proxy configuration for mdsd. Format: "http://username:password@proxy_host:proxy_port". "http:" part is optional. You may specify username and password here. If this is specified both on public and protected configurations, this protected configuration will prevail.

```json
{
  "storageAccountName": "<storage-account-name>",
  "storageAccountKey": "<storage-account-key>",
  "mdsdHttpProxy":"http://proxy_username:password@your_proxy_host:3128"
}
```

Note that the `storageAccountKey` property may be deprecated in the near future. We strongly recommend that an account SAS token is given as follows:

```json
{
  "storageAccountName": "<storage-account-name>",
  "storageAccountSasToken": "<storage-account-sas-token>",
  "mdsdHttpProxy":"http://proxy_username:password@your_proxy_host:3128"
}
```

An account SAS token should be of the following format:

```
sv=2015-12-11&ss=bt&srt=co&sp=wlacu&st=2016-11-09T00%3A04%3A00Z&se=9999-11-10T00%3A04%3A00Z&sig=[signed-signature-string]
```

Details on how to construct an account SAS token can be found in
[this document](https://msdn.microsoft.com/en-us/library/azure/mt584140.aspx). If you need
to manually generate an account SAS token, we recommend using
[the Microsoft Azure Storage Explorer](http://storageexplorer.com/). Just install/run
the Explorer, login with your Azure account (or add a storage account explicitly),
right-click on the storage account for which you want to generate an account SAS token,
and click Get Shared Access Signature and follow the dialog.

In order for the given account SAS to work with the Linux Azure Diagnostic extension,
the following requirements must be met:

* Services (ss) must include Blobs (b) and Tables (t).
* Permissions (sp) must include Write (w), List (l), Add (a), Create (c), and Update (u).
* Resource Types (srt) must include Container (c) and Object (o).
* Start time (st) and Expiry time (se) should be valid for the duration of time
the SAS will be used. We recommend to set the Start time with today's date and
to set the Expiry time with the date 9999-12-31. 

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

You can deploy Diagnostic Extension by running:
```
$ azure vm extension set <vm-name> LinuxDiagnostic Microsoft.OSTCExtensions '2.*' -c public.json -e protected.json
```

In the command above, you can change version with `'*'` to use latest version available, or `'2.*'` to get newest version that does not introduce non-breaking schema changes.


#### 2.1.2 Resource Manager
You can change to Azure Resource Manager mode by running:
```
$ azure config mode arm
```

You can deploy Diagnostic Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> LinuxDiagnostic Microsoft.OSTCExtensions <version> -c public.json  -e protected.json
```

### 2.2. Using [**Azure Powershell**][azure-powershell]

#### 2.2.1 Classic

You can login to your Azure account (Azure Service Management mode) by running:

```powershell
Add-AzureAccount
```

You can deploy Diagnostic Extension by running:

```powershell
$VmName = '<vm-name>'
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$ExtensionName = 'LinuxDiagnostic'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '<version>'

# Add "mdsdHttpProxy" setting to $PublicConf or $PrivateConf as needed (as mentioned above)

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
  "enableSyslog":"true"
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

You can deploy LinuxDiagnostic Extension by running:

```powershell
$RGName = '<resource-group-name>'
$VmName = '<vm-name>'
$Location = '<location>'

$ExtensionName = 'LinuxDiagnostic'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '<version>'

# Add "mdsdHttpProxy" setting to $PublicConf or $PrivateConf if needed (as mentioned above).

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
  "enableSyslog":"true"
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

Add "mdsdHttpProxy" setting to "settings" section or "protectedSettings" section if needed (as mentioned above).

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
    "typeHandlerVersion": "2.3",
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

Please note that the distros/versions listed below apply only to Azure-endorsed Linux vendor
images. 3rd party BYOL/BYOS images (e.g., appliances) are not generally supported for the
Linux Diagnostic extension.

- Ubuntu 12.04 and higher. Ubuntu 16.04 support is currently not official, as our OMI dependency is not officially supported on Ubuntu 16.04 as of LAD 2.3.9. Also as of the same version, MySQL monitoring using OMI/SCX is not working on Ubuntu 16.04, due to the fact that Ubuntu 16.04's MySQL build is changed in a way that current OMI/SCX doesn't support.
- CentOS 6.5 and higher
- Oracle Linux 6.4.0.0.0 and higher
- OpenSUSE 13.1 and higher
- SUSE Linux Enterprise Server 11 and higher
- Debian 7 and higher (7 is now supported with static mdsd build)
- RHEL 6.7 and higher

## Debug

* The status of the extension is reported back to Azure so that user can see the status on Azure Portal
* The operation log of the extension is `/var/log/azure/Microsoft.OSTCExtensions.LinuxDiagnostic/<version>/` directory.

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
