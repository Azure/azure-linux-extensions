# Custom Script Extension
Allow the owner of the Azure VM to run customized scripts.
## Features
* It can be installed using Azure PowerShell, Azure CLI or Azure Management Portal
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

## Version
1.3

## Configuration
### Public Configuration
```javascript
{
  "fileUris": ["<url>"],
  "commandToExecute": "<command-to-execute>"
}
```

For "commandToExecute", there are three acceptable formats.
* Specify the interpreter
```
"commandToExecute": "sh myscript.sh"
```
* If Shebang("#!") is specified
```
"commandToExecute": "./myscript.sh" 
```
* Inline commands
```
"commandToExecute": "echo Hello"
```
```
"commandToExecute": "python -c \"print 1.3\""
```
### Private Configuration
```javascript
{
  "storageAccountName": "<storage-account-name>",
  "storageAccountKey": "<storage-account-key>"
}
```

## Install CustomScript Extension
### Xplat-cli Sample
To learn how to install and configure the Azure CLI, visit [Install and Configure the Azure CLI](https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/#how-to-install-the-azure-cli).

```
azure vm extension set <resource-group> <vm-name> CustomScriptForLinux Microsoft.OSTCExtensions <version> -i '{"fileUris":["<url>"], "commandToExecute": "<command>" }' -f '{"storageAccountName":"<storage-account-name>","storageAccountKey":"<storage-account-key>"}'
```
You can also put your configuration in a json file as the following, and pass the path to Azure CLI.
```
{
  "fileUris": [
    "https://raw.githubusercontent.com/Azure/azure-linux-extensions/master/CustomScript/README.md"
  ],
  "commandToExecute": "echo hello",
  "timestamp": 1438929795
}
```
```
azure vm extension set <resource-group> <vm-name> CustomScriptForLinux Microsoft.OSTCExtensions <version> -c <path-to-public-configuration> -e <path-to-private-configuration>
```

* If you need to run the same script repeatly, you can add a timestamp
in the "-i" parameter.
```bash
$ data +%s
1438929794
$ azure vm extension set <resource-group> <vm-name> CustomScriptForLinux Microsoft.OSTCExtensions <version> -i '{"fileUris":["<url>"], "commandToExecute": "<command>", "timestamp": 1438929794 }' -f '{"storageAccountName":"<storage-account-name>","storageAccountKey":"<storage-account-key>"}'
```

### PowerShell Sample
```powershell
$ExtensionName = 'CustomScriptForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = <version>

$VmName = '<vm-name>'
Write-Host ('Retrieving the VM ' + $VmName + '.....................')
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$PublicConf = '{
    "fileUris": ["<url>"],
    "commandToExecute": "<command>"
}'
$PrivateConf = '{
    "storageAccountName": "<storage-account-name>",
    "storageAccountKey": "<storage-account-key>"
}'

Write-Host ('Deploying the extension ' + $ExtensionName + ' with Version ' + $Version + ' on ' + $VmName + '.....................')
Set-AzureVMExtension -ExtensionName $ExtensionName -VM  $vm -Publisher $Publisher -Version $Version -PrivateConfiguration $PrivateConf -PublicConfiguration $PublicConf | Update-AzureVM
```

* If you need to run the same script repeatly, you can add a timestamp
in the "-PublicConfiguration" parameter.
```powershell
$TimeStamp = (Get-Date).Ticks
-PublicConfiguration '{"fileUris":["<url>"], "commandToExecute": "<command>", "timestamp": $TimeStamp}'
```

## More Information
To learn more information about the usage of CustomScript Extension, please visit [Automate Linux VM Customization Tasks Using CustomScript Extension](http://azure.microsoft.com/blog/2014/08/20/automate-linux-vm-customization-tasks-using-customscript-extension/).
