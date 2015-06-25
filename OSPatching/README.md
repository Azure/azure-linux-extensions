# OS Patching Extension
Allow the owner of the Azure VM to configure the Linux VM patching schedule
cycle. And the actual patching operation is automated based on the
pre-configured schedule.
## Features
* it can be installed through Azure RESTFUL API for extension
* it supports major Linux
* it can be configured by the user
* it can patch the os automatically as a scheduled task
* it can patch the os automatically as a one-off
* status of the extension is reported back to Azure so that
you can see the status on Azure Portal
* it can be stopped before the actual patching operation
* the status of VM can be checked by user-defined scripts,
which can be stored locally, in github or Azure Storage

## Prepare
Add-Add-AzureAccount
Select-AzureSubscription -SubscriptionName '<your_subscription_name>'

## Usage
PowerShell script to deploy the extension on VM
```powershell
$ExtensionName = 'OSPatchingForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version =  '2.0'

$VmName = '<vm_name>'
Write-Host ('Retrieving the VM ' + $VmName + '.....................')
$vm = get-azurevm $VmName

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

Write-Host ('Deploying the extension ' + $ExtensionName + ' with Version ' + $Version + ' on ' + $VmName + '.....................')
Set-AzureVMExtension -ExtensionName $ExtensionName -VM $vm -Publisher $Publisher -Version $Version -PrivateConfiguration $PrivateConfig -PublicConfiguration $PublicConfig | Update-AzureVM
```

## Limitation
* If you need to run the same script repeatly, you have to add a timestamp in the "-PublicConfiguration" parameter, for example:
```powershell
$TimeStamp = (Get-Date).Ticks
$PublicConfig = ConvertTo-Json -InputObject @{
    <Other-Configuration>;
    "timestamp" = $TimeStamp
}
```

* If the scheduled task can not run on some redhat distro, there may be
a selinux-policy problem. Please refer to
[https://bugzilla.redhat.com/show_bug.cgi?id=657104](https://bugzilla.redhat.com/show_bug.cgi?id=657104)