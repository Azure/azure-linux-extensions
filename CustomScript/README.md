# CustomScript Extension
Allow the owner of the Azure Virtual Machines to run customized scripts in the VM.

Latest version is 1.4.

You can read the User Guide below.
* [Learn more: Azure Virtual Machine Extensions](https://msdn.microsoft.com/en-us/library/azure/dn606311.aspx)

CustomScript Extension can:
* If provided, download the customized scripts from Azure Storage or external public storage (e.g. Github)
* Run the entrypoint script
* Support inline command
* Convert Windows style newline in Shell and Python scripts automatically
* Remove BOM in Shell and Python scripts automatically
* Protect sensitive data in `commandToExecute`


# User Guide

## 1. Configuration schema

### 1.1. Public configuration

Schema for the public configuration file looks like this:

* `fileUris`: (optional, string array) the uri list of the scripts
* `commandToExecute`: (required, string) the entrypoint script to execute
 
```json
{
  "fileUris": ["<url>"],
  "commandToExecute": "<command-to-execute>"
}
```

### 1.2. Protected configuration

Schema for the protected configuration file looks like this:

* `commandToExecute`: (optional, string) the entrypoint script to execute
* `storageAccountName`: (optional, string) the name of storage account
* `storageAccountKey`: (optional, string) the access key of storage account

```json
{
  "commandToExecute": "<command-to-execute>",
  "storageAccountName": "<storage-account-name>",
  "storageAccountKey": "<storage-account-key>"
}
```

**NOTE:**

1. The storage account here is to store the scripts in `fileUris`.
If the scripts are stored in the private Azure Storage, you should provide
`storageAccountName` and `storageAccountKey`. You can get these two values from Azure Portal.
2. `commandToExecute` in protected settings can protect your sensitive data.
But `commandToExecute` should not be specified both in public and protected configurations.

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.

**NOTE:**

Creating VM in Azure has two deployment model: Classic and [Resource Manager][arm-overview].
In diffrent models, the deploying commands have different syntaxes. Please select the right
one in section 2.1 and 2.2 below.
 
### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying CustomScript Extension, you should configure your `public.json` and `protected.json`
(in section 1.1 and 1.2 above).

#### 2.1.1 Classic
The Classic mode is also called Azure Service Management mode. You can change to it by running:
```
$ azure config mode asm
```

You can deploying CustomScript Extension by running:
```
$ azure vm extension set <vm-name> \
CustomScriptForLinux Microsoft.OSTCExtensions <version> \
--public-config-path public.json  \
--private-config-path protected.json
```

In the command above, you can change version with `'*'` to use latest
version available, or `'1.*'` to get newest version that does not introduce non-
breaking schema changes. To learn the latest version available, run:
```
$ azure vm extension list
```
You can also omit `--private-config-path` if you do not want to configure those settings.

#### 2.1.2 Resource Manager
You can change to Azure Resource Manager mode by running:
```
$ azure config mode arm
```

You can deploying CustomScript Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> \
CustomScriptForLinux Microsoft.OSTCExtensions <version> \
--public-config-path public.json  \
--private-config-path protected.json
```

> **NOTE:** In ARM mode, `azure vm extension list` is not available for now.


### 2.2. Using [**Azure Powershell**][azure-powershell]

#### 2.2.1 Classic
You can change to Azure Service Management mode by running:
```powershell
Switch-AzureMode -Name AzureServiceManagement
```

You can deploying CustomScript Extension by running:
```powershell
$VmName = '<vm-name>'
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$ExtensionName = 'CustomScriptForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = <version>

$PublicConf = '{
    "fileUris": ["<url>"],
    "commandToExecute": "<command>"
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
You can change to Azure Resource Manager mode by running:
```powershell
Switch-AzureMode -Name AzureResourceManager
```

You can deploying CustomScript Extension by running:
```powershell
$RGName = '<resource-group-name>'
$VmName = '<vm-name>'
$Location = '<location>'

$ExtensionName = 'CustomScriptForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = <version>

$PublicConf = '{
    "fileUris": ["<url>"],
    "commandToExecute": "<command>"
}'
$PrivateConf = '{
    "storageAccountName": "<storage-account-name>",
    "storageAccountKey": "<storage-account-key>"
}'

Set-AzureVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher `
  -ExtensionType $ExtensionName -TypeHandlerVersion $Version `
  -Settingstring $PublicConf -ProtectedSettingString $PrivateConf
```

For more details about Set-AzureVMExtension syntax in ARM mode, please visit [Set-AzureVMExtension][Set-AzureVMExtension-ARM].

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
    "publisher": "Microsoft.OSTCExtensions",
    "type": "CustomScriptForLinux",
    "typeHandlerVersion": "1.4",
    "settings": {
      "fileUris": [
        "<url>"
      ],
      "commandToExecute": "<command>"
    },
    "protectedSettings": {
      "storageAccountName": "<storage-account-name>",
      "storageAccountKey": "<storage-account-key>"
    }
  }
}
```

There are two sample templates in [Azure/azure-quickstart-templates](https://github.com/Azure/azure-quickstart-templates).

* [201-customscript-extension-public-storage-on-ubuntu](https://github.com/Azure/azure-quickstart-templates/tree/master/201-customscript-extension-public-storage-on-ubuntu)
* [201-customscript-extension-azure-storage-on-ubuntu](https://github.com/Azure/azure-quickstart-templates/tree/master/201-customscript-extension-azure-storage-on-ubuntu)

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).

## 3. Scenarios

### 3.1 Run scripts stored in Azure Storage

* Public configuration

  ```json
  {
    "fileUris": ["http://MyAccount.blob.core.windows.net/vhds/MyShellScript.sh"],
    "commandToExecute": " sh MyShellScript.sh"
  }
  ```

* Protected configuration

  ```json
  {
    "storageAccountName": "MyAccount",
    "storageAccountKey": "Mykey"
  }
  ```

### 3.2 Run scripts stored in GitHub

* Public configuration

  ```json
  {
    "fileUris": ["https://github.com/MyProject/Archive/MyPythonScript.py"],
    "commandToExecute": "python MyPythonScript.py"
  }
  ```

No need to provide protected settings.

### 3.3 Run inline scripts

* Public configuration

  ```json
  "commandToExecute": "echo Hello"
  "commandToExecute": "python -c \"print 1.4\""
  ```

### 3.4 Run scripts with unchanged configurations

Running scripts with the exactly same configurations is unaccepted in current design.
If you need to run scripts repeatly, you can add a timestamp.

* Public configuration

  ```json
  {
    "fileUris": ["<url>"],
    "commandToExecute": "<command>",
    "timestamp": 123456789
  }
  ```

### 3.5 Run scripts with sensitive data

* Public configuration

  ```json
  {
    "fileUris": ["https://github.com/MyProject/Archive/MyPythonScript.py"]
  }
  ```

* Protected configuration

  ```json
  {
    "commandToExecute": "python MyPythonScript.py <my-password>"
  }
  ```

## Supported Linux Distributions
- Ubuntu 12.04 and higher
- CentOS 6.5 and higher
- Oracle Linux 6.4.0.0.0 and higher
- openSUSE 13.1 and higher
- SUSE Linux Enterprise Server 11 SP3 and higher
- FreeBSD

## Debug

* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* All the execution output and error of the scripts are logged into
the download directory of the scripts
`/var/lib/waagent/<extension-name-and-version>/download/<seq>/`,
and the tail of the output is logged into the log directory specified
in HandlerEnvironment.json and reported back to Azure
* The operation log of the extension is `/var/log/azure/<extension-name>/<version>/extension.log` file.

## Changelog

### v1.4 11/19/2015
Protect sensitive data in `commandToExecute`

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
[Set-AzureVMExtension-ARM]: https://msdn.microsoft.com/en-us/library/mt163544.aspx
