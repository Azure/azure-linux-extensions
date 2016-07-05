# OSPatching Extension
Allow the owner of the Azure VM to configure the Linux VM patching schedule
cycle. And the actual patching operation is automated based on the
pre-configured schedule.

Lastest version is 2.0.

You can read the User Guide below.
* [Automate Linux VM OS Updates Using OSPatching Extension (outdated, needs to update)](http://azure.microsoft.com/blog/2014/10/23/automate-linux-vm-os-updates-using-ospatching-extension/)

OSPatching Extension can:
* Patch the OS automatically as a scheduled task
* Patch the OS automatically as a one-off
* it can be stopped before the actual patching operation
* the status of VM can be checked by user-defined scripts,
which can be stored locally, in github or Azure Storage

# User Guide

## 1. Configuration schema

### 1.1. Public configuration

Schema for the public configuration file looks like this:

| Name | Description | Value Type | Default Value |
|:---|:---|:---|:---|
| disabled | Flag to disable this extension | required, boolean | false |
| stop | Flag to cancel the OS update process | required, boolean | false |
| rebootAfterPatch | The reboot behavior after patching | optional, string | RebootIfNeed |
| category | Type of patches to install | optional, string | Important |
| installDuration | The allowed total time for installation | optional, string | 01:00 |
| oneoff | Patch the OS immediately | optional, boolean | false |
| intervalOfWeeks | The update frequency (in weeks) | optional, string | 1 |
| dayOfWeek | The patching date (of the week)You can specify multiple days in a week | optional, string | Everyday |
| startTime | Start time of patching | optional, string | 03:00 |
| distUpgradeList | Path to a repo list which for which a full upgrade (e.g. dist-upgrade in Ubuntu) will occur | optional, string | /etc/apt/sources.list.d/custom.list |
| distUpgradeAll | Flag to enable full upgrade (e.g. dist-upgrade in Ubuntu) for all repos/packages. Disabled (False) by default | optional, bool | True |
| vmStatusTest | Including `local`, `idleTestScript` and `healthyTestScript` | optional, object | |
| local | Flag to assign the location of user-defined scripts | optional, boolean | false |
| idleTestScript | If `local` is true, it is the contents of the idle test script. Otherwise, it is the uri of the idle test script. | optional, string | |
| healthyTestScript | If `local` is true, it is the contents of the healthy test script. Otherwise, it is the uri of the healthy test script. | optional, string | |
  
 
```json
{
  "disabled": false,
  "stop": false,
  "rebootAfterPatch": "RebootIfNeed|Required|NotRequired|Auto",
  "category": "Important|ImportantAndRecommended",
  "installDuration": "<hr:min>",
  "oneoff": false,
  "intervalOfWeeks": "<number>",
  "dayOfWeek": "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Everyday",
  "startTime": "<hr:min>",
  "distUpgradeList": "</etc/apt/sources.list.d/custom.list>",
  "vmStatusTest": {
    "local": false,
    "idleTestScript": "<path_to_idletestscript>",
    "healthyTestScript": "<path_to_healthytestscript>"
  }
}
```

### 1.2. Protected configuration

Schema for the protected configuration file looks like this:

* `storageAccountName`: (optional, string) the name of storage account
* `storageAccountKey`: (optional, string) the access key of storage account

```json
{
  "storageAccountName": "<storage-account-name>",
  "storageAccountKey": "<storage-account-key>"
}
```

If the vmStatusTest scripts are stored in the private Azure Storage, you should provide
`storageAccountName` and `storageAccountKey`. You can get these two values from Azure Portal.

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.

> **NOTE:** Creating VM in Azure has two deployment model: Classic and [Resource Manager][arm-overview].
In diffrent models, the deploying commands have different syntaxes. Please select the right
one in section 2.1 and 2.2 below.
 
### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying OSPatching Extension, you should configure your `public.json` and `protected.json`
(in section 1.1 and 1.2 above).

#### 2.1.1 Classic
The Classic mode is also called Azure Service Management mode. You can change to it by running:
```
$ azure config mode asm
```

You can deploying OSPatching Extension by running:
```
$ azure vm extension set <vm-name> \
OSPatchingForLinux Microsoft.OSTCExtensions <version> \
--public-config-path public.json  \
--private-config-path protected.json
```

In the command above, you can change version with `"*"` to use latest
version available, or `"1.*"` to get newest version that does not introduce non-
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

You can deploying OSPatching Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> \
OSPatchingForLinux Microsoft.OSTCExtensions <version> \
--public-config-path public.json  \
--private-config-path protected.json
```

> **NOTE:** In ARM mode, `azure vm extension list` is not available for now.


### 2.2. Using [**Azure Powershell**][azure-powershell]

#### 2.2.1 Classic

You can login to your Azure account (Azure Service Management mode) by running:

```powershell
Add-AzureAccount
```

You can deploying OSPatching Extension by running:

```powershell
$VmName = '<vm-name>'
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$ExtensionName = 'OSPatchingForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '<version>'

$idleTestScriptUri = '<path_to_idletestscript>'
$healthyTestScriptUri = '<path_to_healthytestscript>'

$PublicConfig = ConvertTo-Json -InputObject @{
    "disabled" = $false;
    "stop" = $true|$false;
    "rebootAfterPatch" = "RebootIfNeed|Required|NotRequired|Auto";
    "category" = "Important|ImportantAndRecommended";
    "installDuration" = "<hr:min>";
    "oneoff" = $true|$false;
    "intervalOfWeeks" = "<number>";
    "dayOfWeek" = "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Everyday";
    "startTime" = "<hr:min>";
    "vmStatusTest" = (@{
        "local" = $false;
        "idleTestScript" = $idleTestScriptUri;
        "healthyTestScript" = $healthyTestScriptUri
    })
}

# Optional
# If you use azure storage, you have to offer the key
$PrivateConfig = ConvertTo-Json -InputObject @{
    "storageAccountName" = "<storage_account_name>";
    "storageAccountKey" = "<storage_account_key>"
}

Set-AzureVMExtension -ExtensionName $ExtensionName -VM $vm `
  -Publisher $Publisher -Version $Version `
  -PrivateConfiguration $PrivateConfig -PublicConfiguration $PublicConfig |
  Update-AzureVM
```

#### 2.2.2 Resource Manager

You can login to your Azure account (Azure Resource Manager mode) by running:

```powershell
Login-AzureRmAccount
```

Click [**HERE**](https://azure.microsoft.com/en-us/documentation/articles/powershell-azure-resource-manager/) to learn more about how to use Azure PowerShell with Azure Resource Manager.

You can deploying OSPatching Extension by running:

```powershell
$RGName = '<resource-group-name>'
$VmName = '<vm-name>'
$Location = '<location>'

$ExtensionName = 'OSPatchingForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '<version>'

$PublicConf = ConvertTo-Json -InputObject @{
    "disabled" = $false;
    "stop" = $true|$false;
    "rebootAfterPatch" = "RebootIfNeed|Required|NotRequired|Auto";
    "category" = "Important|ImportantAndRecommended";
    "installDuration" = "<hr:min>";
    "oneoff" = $true|$false;
    "intervalOfWeeks" = "<number>";
    "dayOfWeek" = "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Everyday";
    "startTime" = "<hr:min>";
    "vmStatusTest" = (@{
        "local" = $false;
        "idleTestScript" = $idleTestScriptUri;
        "healthyTestScript" = $healthyTestScriptUri
    })
}

# Optional
# If you use azure storage, you have to offer the key
$PrivateConf = ConvertTo-Json -InputObject @{
    "storageAccountName" = "<storage_account_name>";
    "storageAccountKey" = "<storage_account_key>"
}

Set-AzureRmVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher -ExtensionType $ExtensionName `
  -TypeHandlerVersion $Version -Settingstring $PublicConf -ProtectedSettingString $PrivateConf
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
    "publisher": "Microsoft.OSTCExtensions",
    "type": "OSPatchingForLinux",
    "typeHandlerVersion": "2.0",
    "settings": {
      "disabled": false,
      "stop": false,
      "rebootAfterPatch": "RebootIfNeed|Required|NotRequired|Auto",
      "category": "Important|ImportantAndRecommended",
      "installDuration": "<hr:min>",
      "oneoff": false,
      "intervalOfWeeks": "<number>",
      "dayOfWeek": "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Everyday",
      "startTime": "<hr:min>",
      "vmStatusTest": {
        "local": false,
        "idleTestScript": "<path_to_idletestscript>",
        "healthyTestScript": "<path_to_healthytestscript>"
      }
    },
    "protectedSettings": {
      "storageAccountName": "<storage-account-name>",
      "storageAccountKey": "<storage-account-key>"
    }
  }
}
```

The sample ARM template is [201-ospatching-extension-on-ubuntu](https://github.com/Azure/azure-quickstart-templates/tree/master/201-ospatching-extension-on-ubuntu).

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).

## 3. Scenarios

### 3.1 Setting up scheduled patching
For regular recurring patching, you can configure the schedule as the following. And you can modify existing patching configurations and re-enable it.
* Public Settings
```json
{
  "disabled": false,
  "stop": false,
  "rebootAfterPatch": "RebootIfNeed",
  "intervalOfWeeks": "1",
  "dayOfWeek": "Sunday|Wednesday",
  "startTime": "03:00",
  "category": "ImportantAndRecommended",
  "installDuration": "00:30"
}
```
No need to provide protected settings.

### 3.2 Setting up one-off patching

* Public Settings
```json
{
  "disabled": false,
  "stop": false,
  "rebootAfterPatch": "RebootIfNeed",
  "one-off": true,
  "category": "ImportantAndRecommended",
  "installDuration": "00:30"
}
```
No need to provide protected settings.

### 3.3 Stop the running patching
You can stop the OS updates for debugging. Once the “stop” parameter is set to “true”, the OS update will stop after the current update is finished.
* Public Settings
```json
{
  "disabled": false,
  "stop": true  
}
```

### 3.4 Test the idle before patching and the health after patching
* Public Settings
```json
{
  "disabled": false,
  "stop": false,
  "rebootAfterPatch": "RebootIfNeed",
  "category": "ImportantAndRecommended",
  "installDuration": "00:30",
  "oneoff": false,
  "intervalOfWeeks": "1",
  "dayOfWeek": "Sunday|Wednesday",
  "startTime": "03:00",
  "vmStatusTest": {
    "local": false,
    "idleTestScript": "<path_to_idletestscript>",
    "healthyTestScript": "<path_to_healthytestscript>"
  }
}
```
If the `vmStatusTest` scripts are stored in Azure Storage private containers, you have to provide the `storageAccountName` and `storageAccountKey`.
* Protected Settings
```json
{
  "storageAccountName": "MyAccount",
  "storageAccountKey": "Mykey"
}
```

### 3.5 Enable the extension repeatly
Enabling the extension with the exactly same configurations is unaccepted in current design.
If you need to run scripts repeatly, you can add a timestamp.

```json
"timestamp": 123456789
```

### 3.6 Disable the extension
If you want to switch to manual OS update temporarily, you can set the `disable` parameter to `true` which won't uninstall the OSPatching extension.

## Supported Linux Distributions
- Ubuntu 12.04 and higher
- CentOS 6.5 and higher
- Oracle Linux 6.4.0.0.0 and higher
- openSUSE 13.1 and higher
- SUSE Linux Enterprise Server 11 SP3 and higher

## Debug

* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* The operation log of the extension is `/var/log/azure/<extension-name>/<version>/extension.log` file.

# Known Issues
* If the scheduled task can not run on some redhat distro, there may be
a selinux-policy problem. Please refer to
[https://bugzilla.redhat.com/show_bug.cgi?id=657104](https://bugzilla.redhat.com/show_bug.cgi?id=657104)

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
