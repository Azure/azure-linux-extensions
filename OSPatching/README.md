# :warning: IMPORTANT :warning:
**The OSPatching extension for Linux is deprecated.**

OSPatchingForLinux is deprecated and will be retired February 2018.

Your Linux distro has well supported and maintained ways to enable automatic updates
for your VMs to include VMs you use in Production environments. It is recommended
that you consult your distro's best practices for automatic updates.

## Linux Distributions
- Ubuntu
  - See the [unattended-upgrades](https://help.ubuntu.com/lts/serverguide/automatic-updates.html) package documentation
- CentOS and RHEL
  - See the manpage of `yum-cron` for the auto-update mechanism documentation


# OSPatching Extension
Allows the owner of the Azure VM to configure a Linux VM patching schedule cycle
or perform OS patching on-demand as a one-time task. The actual patching operation
is scheduled as a cron job.

Lastest version is 2.3.

You can read the User Guide, [Automate Linux VM OS Updates Using OSPatching Extension (outdated, needs to update)](http://azure.microsoft.com/blog/2014/10/23/automate-linux-vm-os-updates-using-ospatching-extension/).

OSPatching Extension can:
* Patch the OS automatically as a scheduled task
* Patch the OS as a one-time task
* The patching can be stopped before the actual patching operation begins
* The status of VM can be checked by user-defined scripts stored locally, in GitHub, or in Azure Storage

# User Guide

## 1. Configuration schema
All settings are set in the protected configuration. No settings are available in the public configuration and it can be omitted.

### 1.1. Protected configuration
Schema for the protected configuration file.

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
| storageAccountName | The name of the storage account | optional, string | |
| storageAccountKey | The access key of the storage account | optional, string | |
  
If the vmStatusTest scripts are stored in the private Azure Storage, you must provide
`storageAccountName` and `storageAccountKey`. You can get these two values from Azure Portal.
 
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
  },
  "storageAccountName": "<storage-account-name>",
  "storageAccountKey": "<storage-account-key>"
}
```

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.

> **NOTE:** Creating VM in Azure has two deployment model: Classic and [Resource Manager][arm-overview].
In diffrent models, the deploying commands have different syntaxes. Please select the right
one in section 2.1 and 2.2 below.
 
### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying OSPatching Extension, you should configure your `protected.json` (in section 1.1 above).

#### 2.1.1 Classic
The Classic mode is also called Azure Service Management mode. You can change to it by running:
```
$ azure config mode asm
```

You can deploying OSPatching Extension by running:
```
$ azure vm extension set <vm-name> \
OSPatchingForLinux Microsoft.OSTCExtensions <version> \
--private-config-path protected.json
```

In the command above, you can change version with `"*"` to use latest
version available, or `"2.*"` to get newest version that does not introduce non-
breaking schema changes. To find the latest version available, run:
```
$ azure vm extension list
```

#### 2.1.2 Resource Manager
You can change to Azure Resource Manager mode by running:
```
$ azure config mode arm
```

You can deploy OSPatching Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> \
OSPatchingForLinux Microsoft.OSTCExtensions <version> \
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

$PrivateConfig = ConvertTo-Json -InputObject @{
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
    });
    "storageAccountName" = "<storage_account_name>";
    "storageAccountKey" = "<storage_account_key>"
}

Set-AzureVMExtension -ExtensionName $ExtensionName -VM $vm `
  -Publisher $Publisher -Version $Version `
  -PrivateConfiguration $PrivateConfig |
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

$PrivateConf = ConvertTo-Json -InputObject @{
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
    });
    "storageAccountName" = "<storage_account_name>";
    "storageAccountKey" = "<storage_account_key>"
}

Set-AzureRmVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher -ExtensionType $ExtensionName `
  -TypeHandlerVersion $Version -ProtectedSettingString $PrivateConf
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
    "protectedSettings": {
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
      },
      "storageAccountName": "<storage-account-name>",
      "storageAccountKey": "<storage-account-key>"
    }
  }
}
```

The sample ARM template is [201-ospatching-extension-on-ubuntu](https://github.com/Azure/azure-quickstart-templates/tree/master/201-ospatching-extension-on-ubuntu).

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).

## 3. Scenarios

### 3.1 Setting up regularly scheduled patching
**Protected Settings**
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

### 3.2 Setting up one-off patching
**Protected Settings**
```json
{
  "disabled": false,
  "stop": false,
  "rebootAfterPatch": "RebootIfNeed",
  "oneoff": true,
  "category": "ImportantAndRecommended",
  "installDuration": "00:30"
}
```

### 3.3 Stop the running patching
You can stop the OS updates to debug issues. Once the `stop` parameter is set to `true`, the OS update will stop after the current update is finished.

**Protected Settings**
```json
{
  "disabled": false,
  "stop": true  
}
```

### 3.4 Test the idle before patching and the health after patching
If the `vmStatusTest` scripts are stored in Azure Storage private containers, you have to provide the `storageAccountName` and `storageAccountKey`.

**Protected Settings**
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
  },
  "storageAccountName": "MyAccount",
  "storageAccountKey": "Mykey"
}
```

### 3.5 Enable the extension repeatedly
Enabling the OSPatching Extension with the exact same configuration is unsupported and will result in
a no-op (nothing will happen). If you need to run scripts repeatedly, you can add a timestamp.

```json
"timestamp": 123456789
```

### 3.6 Disable the extension
If you want to switch to manual OS update temporarily, you can set the `disable` parameter to `true` instead of uninstalling the OSPatching Extension.

## Debugging
* The operation log of the extension is `/var/log/azure/<extension-name>/<version>/extension.log` file.
* The installation status of the extension is reported back to Azure so that the user can see the status on Azure Portal.
  This does not mean the OSPatching Extension successfully applied the current configuration to the VM.
* Attempting to enable the OSPatching Extension 2 or more times with the same configuration will result in nothing happening.
  See [Enable the extension repeatedly](#3.5 Enable the extension repeatedly) section above for more details.

# Known Issues
* If the scheduled task does not run on some RedHat distros, there may be a selinux-policy problem. Please refer to
[https://bugzilla.redhat.com/show\_bug.cgi?id=657104](https://bugzilla.redhat.com/show_bug.cgi?id=657104)

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
