# Custom Script Extension
Allow the owner of the Azure VM to run script stored in Azure storage during or
after VM provisioning
## Features
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

## Requirement
Python 2.7+
## Usage
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
## Limitation
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