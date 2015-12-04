# VMAccess Extension
Provide several ways to allow owner of the VM to get the SSH access back.

Current version is 1.3.

You can read the User Guide below.
* [Using VMAccess Extension to Reset Login Credentials, Add New User and Add SSH Key for Linux VM](https://azure.microsoft.com/blog/2014/08/25/using-vmaccess-extension-to-reset-login-credentials-for-linux-vm/)

VMAccess Extension can:
* Reset the password of the original sudo user 
* Create a new sudo user with the password specified
* Set the public host key with the key given
* Reset the public host key provided during VM provisioning if host key not provided
* Open the SSH port(22) and restore the sshd_config if reset_ssh is set to true
* Remove the existing user

# User Guide

## 1. Configuration schema

### 1.1. Public configuration

No need to provide the public configuration.

### 1.2. Protected configuration

Schema for the protected configuration file looks like this:

* `username`: (required, string) the name of the user
* `password`: (optional, string) the password of the user
* `ssh_key`: (optional, string) the public key of the user, base64 encoded pem
* `reset_ssh`: (optional, boolean) whether or not reset the ssh
* `remove_user`: (optional, string) the user name to remove

```json
{
  "username": "<username>",
  "password": "<password>",
  "ssh_key": "<pem-cert-contents>",
  "reset_ssh": true,
  "remove_user": "<username-to-remove>"
}
```

> **NOTE:** Currently, only base64 encoded pem format is supported for `ssh_key`.
It should begin with `-----BEGIN CERTIFICATE-----`.

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.

> **NOTE:** Creating VM in Azure has two deployment model: Classic and [Resource Manager][arm-overview].
In diffrent models, the deploying commands have different syntaxes. Please select the right
one in section 2.1 and 2.2 below.
 
### 2.1. Using [**Azure CLI**][azure-cli]
Before deploying VMAccess Extension, you should configure your `protected.json`
(in section 1.2 above).

#### 2.1.1 Classic
The Classic mode is also called Azure Service Management mode. You can change to it by running:
```
$ azure config mode asm
```

You can deploying VMAccess Extension by running:
```
$ azure vm extension set <vm-name> \
VMAccessForLinux Microsoft.OSTCExtensions <version> \
--private-config-path protected.json
```

In the command above, you can change version with `"*"` to use latest
version available, or `"1.*"` to get newest version that does not introduce non-
breaking schema changes. To learn the latest version available, run:
```
$ azure vm extension list
```

#### 2.1.2 Resource Manager
You can change to Azure Resource Manager mode by running:
```
$ azure config mode arm
```

You can deploying VMAccess Extension by running:
```
$ azure vm extension set <resource-group> <vm-name> \
VMAccessForLinux Microsoft.OSTCExtensions <version> \
--private-config-path protected.json
```

> **NOTE:** In ARM mode, `azure vm extension list` is not available for now.


### 2.2. Using [**Azure Powershell**][azure-powershell]

#### 2.2.1 Classic
You can change to Azure Service Management mode by running:
```powershell
Switch-AzureMode -Name AzureServiceManagement
```

You can deploying VMAccess Extension by running:
```powershell
$VmName = '<vm-name>'
$vm = Get-AzureVM -ServiceName $VmName -Name $VmName

$ExtensionName = 'VMAccessForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = <version>

$PublicConf = '{}'
$PrivateConf = '{
  "username": "<username>",
  "password": "<password>",
  "ssh_key": "<pem-cert-contents>",
  "reset_ssh": true|false,
  "remove_user": "<username-to-remove>"
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

You can deploying VMAccess Extension by running:
```powershell
$RGName = '<resource-group-name>'
$VmName = '<vm-name>'
$Location = '<location>'

$ExtensionName = 'VMAccessForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = <version>

$PublicConf = '{}'
$PrivateConf = '{
  "username": "<username>",
  "password": "<password>",
  "ssh_key": "<pem-cert-contents>",
  "reset_ssh": true|false,
  "remove_user": "<username-to-remove>"
}'

Set-AzureVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher -ExtensionType $ExtensionName `
  -TypeHandlerVersion $Version -Settingstring $PublicConf -ProtectedSettingString $PrivateConf
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
    "type": "VMAccessForLinux",
    "typeHandlerVersion": "1.1",
    "settings": {},
    "protectedSettings": {
      "username": "<username>",
      "password": "<password>",
      "reset_ssh": true,
      "ssh_key": "<ssh-key>",
      "remove_user": "<username-to-remove>"
    }
  }

}
```

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).

## 3. Scenarios

### 3.1 Resetting the password
```json
{
  "username":"currentusername",
  "password":"newpassword"
}
```

### 3.2 Resetting the SSH key
```json
{ 
  "username":"currentusername", 
  "ssh_key":"contentofsshkey",   
}
```

### 3.3 Resetting the password and the SSH key
```json
{
  "username":"currentusername",
  "ssh_key":"contentofsshkey",
  "password":"newpassword",
}
```

### 3.4 Creating a new sudo user account
```json
{
  "username":"newusername",
  "password":"newpassword"
}
```

### 3.5 Resetting the SSH configuration
```json
{
  "reset_ssh": true
}
```

### 3.6 Removing an existing user
```json
{
  "remove_user":"usertoberemoveed",
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
* The operation log of the extension is `/var/log/azure/<extension-name>/<version>/extension.log` file.

## Changelog
### v1.3 Sep. 8, 2015
Add waagent to extension package

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
[Set-AzureVMExtension-ARM]: https://msdn.microsoft.com/en-us/library/mt163544.aspx
