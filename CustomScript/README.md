# Custom Script Extension
Allow the owner of the Azure VM to run script stored in Azure storage during or
after VM provisioning
## Features
* It can be installed using Azure PowerShell Cmdlets, xPlat scripts or Azure Management Portal
* It supports major Linux and FreeBSD distro
* Windows style newline in Shell and Python scripts is converted automatically
* BOM in Shell and Python scripts is removed automatically
* The scripts can be located on Azure Storage or
external public storage (e.g. Github)
* The status of the extension is reported back to Azure so that user can
see the status on Azure Portal
* Support inline command
* All the execution output and error of the scripts are logged into
the download directory of the scripts, and the tail of the output is
logged into the log directory specified in HandlerEnvironment.json
and reported back to Azure

## Requirement
Python 2.7+
## Usage
PowerShell Sample
```powershell
$ExtensionName = 'CustomScriptForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = '1.3'

$VmName = '<vm_name>'
Write-Host ('Retrieving the VM ' + $VmName + '.....................')
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

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

Xplat Sample
```
azure vm extension set <vm_name> CustomScriptForLinux Microsoft.OSTCExtensions 1.3 -i '{"fileUris":["<url>"], "commandToExecute": "<command>" }' -t '{"storageAccountName":"<storage_account_name>","storageAccountKey":"<storage_account_key>"}'
```

## Limitation
* To run a script, you need to specify interpreter in "commandToExecute" field,
or you can use "./myscript.sh" if Shebang("#!") is specified in the script.
```powershell
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "sh myscript.sh"}'
```
```powershell
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "python myscript.py"}'
```

* Here is some examples to run inline commands. You need to specify "python -c"
if they are Python commands.
```powershell
-PublicConfiguration '{"commandToExecute": "echo Hello"}'
```
```powershell
-PublicConfiguration '{"commandToExecute": "python -c \"print 1.3\""}'
```

* If you need to run the same script repeatly, you have to add a timestamp
in the "-PublicConfiguration" parameter.
```powershell
$TimeStamp = (Get-Date).Ticks
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "<command>", "timestamp": $TimeStamp}'
```

## More Information
http://azure.microsoft.com/blog/2014/08/20/automate-linux-vm-customization-tasks-using-customscript-extension/