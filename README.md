# Linux extensions for Microsoft Azure IaaS

This project provides the source code of Linux extensions for Microsoft Azure IaaS

# Extension List

## Custom Script Extension
Allow the owner of the Azure VM to run script stored in Azure storage during or
after VM provisioning
### Features
* It can be installed through Azure RESTFUL API for extension
* It supports major Linux and FreeBSD distro
* Only the Shell and Python scripts are supported
* Windows style newline in Shell and Python scripts is converted automatically
* BOM in Shell and Python scripts is removed automatically
* The scripts can be located on Azure Storage or
external public storage (e.g. Github)
* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* All the execution output and error of the scripts are logged into
the download directory of the scripts, and the tail of the output is
logged into the log directory specified in HandlerEnvironment.json
and reported back to Azure

### Requirement
Python 2.7+
### Usage
PowerShell script to deploy the extension on VM
```powershell
$ExtensionName = 'CustomScriptForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '1.3'

$VmName = '<vm_name>'
Write-Host ('Retrieving the VM ' + $VmName + '.....................')
$vm = get-azurevm $VmName

$PublicConf = '{
    "fileUris":["<url>"],
    "commandToExecute": "<command>"
}'
$PrivateConf = '{
    "storageAccountName": "<storage_account_name>",
    "storageAccountKey":"<storage_account_key>"
}'

Write-Host ('Deploying the extension ' + $ExtensionName + ' with Version ' + $Version + ' on ' + $VmName + '.....................')
Set-AzureVMExtension -ExtensionName $ExtensionName -VM  $vm -Publisher $Publisher -Version $Version -PrivateConfiguration $PrivateConf -PublicConfiguration $PublicConf | Update-AzureVM
```
### Limitation
* To run a script, you need to specify interpreter in "commandToExecute" field,
for example:
```powershell
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "sh myscript.sh"}'
```
```powershell
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "python myscript.py"}'
```
Or, you can use "./myscript.sh" if Shebang("#!") is specified in the script.

* If you need to run the same script repeatly, you have to add a timestamp
in the "-PublicConfiguration" parameter, for example:
```powershell
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "<command>", timestamp:1404807859168}'
```

## VM Access Extension
Provide several ways to allow owner of the VM to get the SSH access back
### Features
* it can be installed through Azure RESTFUL API for extension
* it supports major Linux and FreeBSD distro
* it can reset the password of the original sudo user 
* it can create a new sudo user with the password specified
* it can set the public host key with the key given or it can reset the public host key provided during VM provisioning if host key not provided
* it can open the SSH port(22) and restore the sshd_config if reset_ssh is set to True  
* status of the extension is reported back to Azure so that you can see the status on Azure Portal

### Usage
PowerShell script to deploy the extension on VM	
```powershell
$VmName = '<vm_name>'
Write-Host ('Retrieving the VM ' + $VmName + '.....................')
$vm = get-azurevm $VmName
$UserName = "<user_name>"
$Password = "<password>"
$ExtensionName = '<extension_name>'
$Publisher = '<publisher_name>'
$Version =  '<version>'
$cert = Get-Content "<cert_path>"
$PrivateConfig = '{"username":"' + $UserName + '", "password": "' +  $Password + '", "ssh_key":"' + $cert + '","reset_ssh":"True"}'	
Write-Host ('Deploying the extension ' + $ExtensionName + ' with Version ' + $Version + ' on ' + $VmName + '.....................')
Set-AzureVMExtension -ExtensionName $ExtensionName -VM  $vm -Publisher $Publisher -Version $Version -PrivateConfiguration $PrivateConfig -PublicConfiguration $PublicConfig | Update-AzureVM	
``` 

## OS Patching Extension
Allow the owner of the Azure VM to configure the Linux VM patching schedule cycle and the actual patching operation is automated based on the pre-configured schedule.
### Features
* it can be installed through Azure RESTFUL API for extension
* it supports major Linux
* it can be configured by the user
* it can patch the os automatically as a scheduled task
* it can patch the os automatically as a one-off
* status of the extension is reported back to Azure so that you can see the status on Azure Portal

### Usage
PowerShell script to deploy the extension on VM	
```powershell
$VmName = '<vm_name>'
Write-Host ('Retrieving the VM ' + $VmName + '.....................')
$vm = get-azurevm $VmName
$ExtensionName = '<extension_name>'
$Publisher = '<publisher_name>'
$Version =  '<version>'
$PrivateConfig = '{
                      "disabled": "true|false",
                      "stop" : "true|false",
                      "rebootAfterPatch" : "Required|NotRequired|Auto",
                      "intervalOfWeeks" : "1",
                      "dayOfWeek": "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Everyday",
                      "startTime": "hr:min",
                      "category": "Important|ImportantAndRecommended",
                      "installDuration": "hr:min"
                  }'
Write-Host ('Deploying the extension ' + $ExtensionName + ' with Version ' + $Version + ' on ' + $VmName + '.....................')
$PublicConfig = '{ }'
Set-AzureVMExtension -ExtensionName $ExtensionName -VM $vm -Publisher $Publisher -Version $Version -PrivateConfiguration $PrivateConfig -PublicConfiguration $PublicConfig | Update-AzureVM
Write-Host 'Deploy done!'
``` 

## Test Handler Extension
This extension is an extension example  
