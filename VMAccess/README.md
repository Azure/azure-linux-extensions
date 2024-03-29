# VMAccess Extension
Provide several ways to allow owner of the VM to get the SSH access back and perform additional VM disk check tasks. 

Current version is [1.5](https://github.com/Azure/azure-linux-extensions/releases/tag/VMAccess-1.5.18).

You can read the User Guide below.
* [Manage administrative users, SSH, and check or repair disks on Linux VMs by using the VMAccess extension](https://learn.microsoft.com/en-us/azure/virtual-machines/extensions/vmaccess)

VMAccess Extension can:
* Reset the password of the original sudo user 
* Create a new sudo user with the password specified
* Set the public host key with the key given
* Reset the public host key provided during VM provisioning if host key not provided
* Open the SSH port(22) and reset the sshd_config if reset_ssh is set to true
* Remove the existing user
* Check disks
* Repair added disk
* Remove prior public keys when a new public key is provided
* Restore the original backup sshd_config if restore_backup_ssh is set to true

# Security Notes:
* VMAccess Extension is designed for regaining access to a VM in the event that access is lost. 
* Based on this principle, it will grant sudo permission to the account specified in the username field.
* Do not specify a user in the username field if you do not wish that user to gain sudo permissions.
* Instead, login to the VM and use built-in tools (e.g. usermod, chage, etc) to manage unprivileged users.

# User Guide
## 1. Configuration schema
### 1.1. Public configuration

Schema for the public configuration file looks like:

* `check_disk`: (optional, boolean) whether or not to check disk
* `repair_disk`: (optional, boolean) whether or not to repair disk
* `disk_name`: (boolean) name of disk to repair (required when repair_disk is true)

```json
{
  "check_disk": "true",
  "repair_disk": "true",
  "disk_name": "<disk-name>"
}
```

### 1.2. Protected configuration

Schema for the protected configuration file looks like this:

* `username`: (required, string) the name of the user
* `password`: (optional, string) the password of the user
* `ssh_key`: (optional, string) the public key of the user
* `reset_ssh`: (optional, boolean) whether or not reset the ssh
* `remove_user`: (optional, string) the user name to remove
* `expiration`: (optional, string) expiration of the account, defaults to never, e.g. 2016-01-01.
* `remove_prior_keys`: (optional, boolean) whether or not to remove old SSH keys when adding a new one
* `restore_backup_ssh`: (optional, boolean) whether or not to restore original backed-up sshd config

```json
{
  "username": "<username>",
  "password": "<password>",
  "ssh_key": "<cert-contents>",
  "reset_ssh": true,
  "remove_user": "<username-to-remove>",
  "expiration": "<yyyy-mm-dd>",
  "remove_prior_keys": true,
  "restore_backup_ssh": true
}
```

`ssh_key` supports `ssh-rsa`, `ssh-ed25519` and `.pem` formats.

* If your public key is in `ssh-rsa` format, for example, `ssh-rsa XXXXXXXX`, you can use:

  ```
  "ssh_key": "ssh-rsa XXXXXXXX"
  ```

* If your public key is in `ssh-ed25519` format, for example, `ssh-ed25519 XXXXXXXX`, you can use:

  ```
  "ssh_key": "ssh-ed25519 XXXXXXXX"
  ```

* If your public key is in `.pem` format, use the following UNIX command to convert the .pem file to a value that can be passed in a JSON string:

  ```
  awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' myCert.pem
  ```

  You can use:
  ```
  "ssh_key": "-----BEGIN CERTIFICATE-----\nXXXXXXXXXXXXXXXXXXXXXXXX\n-----END CERTIFICATE-----"
  ```

## 2. Deploying the Extension to a VM

You can deploy it using Azure CLI, Azure Powershell and ARM template.
 
### 2.1. Using [**Azure CLI**][azure-cli]

Create a `settings.json` (optional) and a `protected_settings.json` and run:
```
$ azure vm extension set \
--resource-group <resource-group> \
--vm-name <vm-name> \
--name VMAccessForLinux \
--publisher Microsoft.OSTCExtensions \
--version 1.5 \
--settings settings.json
--protected-settings protected_settings.json
```

To retrieve the deployment state of extensions for a given VM, run:
```
$ azure vm extension list \
--resource-group <resource-group> \
--vm-name <vm-name> -o table
```

### 2.2. Using [**Azure Powershell**][azure-powershell]

You can deploying VMAccess Extension by running:

```powershell
$username = "<username>"
$sshKey = "<cert-contents>"

$settings = @{"check_disk" = $true};
$protectedSettings = @{"username" = $username; "ssh_key" = $sshKey};

Set-AzVMExtension -ResourceGroupName "<resource-group>" -VMName "<vm-name>" -Location "<location>" `
-Publisher "Microsoft.OSTCExtensions" -ExtensionType "VMAccessForLinux" -Name "VMAccessForLinux" `
-TypeHandlerVersion "1.5" -Settings $settings -ProtectedSettings $protectedSettings
```

You can provide and modify extension settings by using strings:

```powershell
$username = "<username>"
$sshKey = "<cert-contents>"

$settingsString = '{"check_disk":true}';
$protectedSettingsString = '{"username":"' + $username + '","ssh_key":"' + $sshKey + '"}';

Set-AzVMExtension -ResourceGroupName "<resource-group>" -VMName "<vm-name>" -Location "<location>" `
-Publisher "Microsoft.OSTCExtensions" -ExtensionType "VMAccessForLinux" -Name "VMAccessForLinux" `
-TypeHandlerVersion "1.5" -SettingString $settingsString -ProtectedSettingString $protectedSettingsString
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
    "type": "VMAccessForLinux",
    "typeHandlerVersion": "1.5",
    "autoUpgradeMinorVersion": true,
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

Refer to the following sample [ARM template](https://github.com/azure/azure-quickstart-templates/tree/master/demos/vmaccess-on-ubuntu).

For more details about ARM template, please visit [Authoring Azure Resource Manager templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/).

## 3. Scenarios

### 3.1 Resetting the password

in the Public Settings
```json
{
  "check_disk": "false"
}
```

> VMAccessForLinux resets and restarts the SSH server if a password is specified. This is necessary if the VM was deployed with public key authentication because the SSH server is not configured to accept passwords.  For this reason, the SSH server's configuration is reset to allow password authentication, and restarted to accept this new configuration.  This behavior can be disabled by setting the reset_ssh value to false.

in the Protected Settings
```json
{
  "username": "currentusername",
  "password": "newpassword",
  "reset_ssh": "false"
}
```

### 3.2 Resetting the SSH key
```json
{ 
  "username": "currentusername", 
  "ssh_key": "contentofsshkey"
}
```

### 3.3 Resetting the password and the SSH key
```json
{
  "username": "currentusername",
  "ssh_key": "contentofsshkey",
  "password": "newpassword",
}
```

### 3.4 Creating a new sudo user account with the password
```json
{
  "username": "newusername",
  "password": "newpassword"
}
```

#### 3.4.1 Creating a new sudo user account with a password and expiration date.
```json
{
  "username": "newusername",
  "password": "newpassword",
  "expiration": "2016-12-31"
}
```

### 3.5 Creating a new sudo user account with the SSH key
```json
{
  "username": "newusername",
  "ssh_key": "contentofsshkey"
}
```

#### 3.5.1 Creating a new sudo user account with the SSH key
```json
{
  "username": "newusername",
  "ssh_key": "contentofsshkey",
  "expiration": "2016-12-31"
}
```

### 3.6 Resetting the SSH configuration
```json
{
  "reset_ssh": true
}
```

### 3.7 Removing an existing user
```json
{
  "remove_user": "usertoberemoveed",
}
```

### 3.8 Checking added disks on VM
```json
{
    "check_disk": "true"
}
```

### 3.9 Fix added disks on a VM
```json
{
    "repair_disk": "true",
    "disk_name": "userdisktofix"
}
```

### 3.10 Removing prior SSH keys (only when provided a new one)
```json
{
    "username": "newusername",
    "ssh_key": "contentofsshkey",
    "remove_prior_keys": true
}
```

### 3.11 Restoring original SSH configuration
```json
{
    "restore_backup_ssh": true
}
```

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

[azure-powershell]: https://azure.microsoft.com/en-us/documentation/articles/powershell-install-configure/
[azure-cli]: https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/
[arm-template]: http://azure.microsoft.com/en-us/documentation/templates/ 
[arm-overview]: https://azure.microsoft.com/en-us/documentation/articles/resource-group-overview/
