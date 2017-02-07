Param(
    [Parameter(Mandatory=$true)]
    [string] $SubscriptionId,
    [Parameter(Mandatory=$true)]
    [string] $AadClientId,
    [Parameter(Mandatory=$true)]
    [string] $AadClientSecret,
    [Parameter(Mandatory=$true)]
    [string] $ResourcePrefix,
    [Parameter(Mandatory=$true)]
    [string] $Username,
    [Parameter(Mandatory=$true)]
    [string] $Password,
    [string] $ExtensionName="AzureDiskEncryptionForLinux",
    [string] $SshPubKey,
    [string] $SshPrivKeyPath,
    [string] $Location="eastus",
    [string] $VolumeType="data",
    [string] $GalleryImage="RedHat:RHEL:7.2",
    [string] $VMSize="Standard_D2"
)

$ErrorActionPreference = "Stop"

Set-AzureRmContext -SubscriptionId $SubscriptionId

Write-Host "Set AzureRmContext successfully"

## Resource Group
$global:ResourceGroupName = $ResourcePrefix + "ResourceGroup"
New-AzureRmResourceGroup -Name $ResourceGroupName -Location $Location

Write-Host "Created ResourceGroup successfully: $ResourceGroupName"

## KeyVault
$global:KeyVaultName = $ResourcePrefix + "KeyVault"

$global:KeyVault = New-AzureRmKeyVault -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName -Location $Location

Write-Host "Created KeyVault successfully: $KeyVaultName"

Set-AzureRmKeyVaultAccessPolicy -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName -ServicePrincipalName $AadClientId -PermissionsToKeys all -PermissionsToSecrets all
Set-AzureRmKeyVaultAccessPolicy -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName -EnabledForDiskEncryption

Write-Host "Set AzureRmKeyVaultAccessPolicy successfully"

Add-AzureKeyVaultKey -VaultName $KeyVaultName -Name "keyencryptionkey" -Destination Software

Write-Host "Added AzureRmKeyVaultKey successfully"

$global:KeyEncryptionKey = Get-AzureKeyVaultKey -VaultName $KeyVault.OriginalVault.Name -Name "keyencryptionkey"

Write-Host "Fetched KeyEncryptionKey successfully"

## Storage
$global:StorageName = ($ResourcePrefix + "Storage").ToLower()
$global:StorageType = "Standard_GRS"
$global:ContainerName = "vhds"

$global:StorageAccount = New-AzureRmStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageName -Type $StorageType -Location $Location

Write-Host "Created StorageAccount successfully: $StorageName"

## Network
$global:PublicIpName = $ResourcePrefix + "PublicIp"
$global:InterfaceName = $ResourcePrefix + "NetworkInterface"
$global:SubnetName = $ResourcePrefix + "Subnet"
$global:VNetName = $ResourcePrefix + "VNet"
$global:VNetAddressPrefix = "10.0.0.0/16"
$global:VNetSubnetAddressPrefix = "10.0.0.0/24"
$global:DomainNameLabel = ($ResourcePrefix + "VM").ToLower()

$global:PublicIp = New-AzureRmPublicIpAddress -Name $PublicIpName -ResourceGroupName $ResourceGroupName -Location $Location -AllocationMethod Dynamic -DomainNameLabel $DomainNameLabel

Write-Host "Created PublicIp successfully: " $PublicIp.DnsSettings.Fqdn.ToString()

$global:SubnetConfig = New-AzureRmVirtualNetworkSubnetConfig -Name $SubnetName -AddressPrefix $VNetSubnetAddressPrefix

Write-Host "Created SubnetConfig successfully: $SubnetName"

$global:VNet = New-AzureRmVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroupName -Location $Location -AddressPrefix $VNetAddressPrefix -Subnet $SubnetConfig

Write-Host "Created AzureRmVirtualNetwork successfully: $VNetName"

$global:Interface = New-AzureRmNetworkInterface -Name $InterfaceName -ResourceGroupName $ResourceGroupName -Location $Location -SubnetId $VNet.Subnets[0].Id -PublicIpAddressId $PublicIp.Id

Write-Host "Created AzureNetworkInterface successfully: $InterfaceName"

## Compute
$global:VMName = $ResourcePrefix + "VM"
$global:ComputerName = $ResourcePrefix + "VM"
$global:OSDiskName = $VMName + "OsDisk"
$global:OSDiskUri = $StorageAccount.PrimaryEndpoints.Blob.ToString() + "vhds/" + $OSDiskName + ".vhd"
$global:DataDisk1Name = $VMName + "DataDisk1"
$global:DataDisk1Uri = $StorageAccount.PrimaryEndpoints.Blob.ToString() + "vhds/" + $DataDisk1Name + ".vhd"
$global:DataDisk2Name = $VMName + "DataDisk2"
$global:DataDisk2Uri = $StorageAccount.PrimaryEndpoints.Blob.ToString() + "vhds/" + $DataDisk2Name + ".vhd"

## Setup local VM object
$SecString = ($Password | ConvertTo-SecureString -AsPlainText -Force)
$Credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList @($Username, $SecString)

Write-Host "Created credentials successfully"

$global:VirtualMachine = New-AzureRmVMConfig -VMName $VMName -VMSize $VMSize

Write-Host "Created AzureRmVMConfig successfully"

$VirtualMachine = Set-AzureRmVMOperatingSystem -VM $VirtualMachine -Linux -ComputerName $ComputerName -Credential $Credential

Write-Host "Set AzureRmVMOperatingSystem successfully"

$PublisherName = $GalleryImage.Split(":")[0]
$Offer = $GalleryImage.Split(":")[1]
$Skus = $GalleryImage.Split(":")[2]

Write-Host "PublisherName: $PublisherName, Offer: $Offer, Skus: $Skus"

$VirtualMachine = Set-AzureRmVMSourceImage -VM $VirtualMachine -PublisherName $PublisherName -Offer $Offer -Skus $Skus -Version "latest"

Write-Host "Set AzureVMSourceImage successfully"

$VirtualMachine = Add-AzureRmVMNetworkInterface -VM $VirtualMachine -Id $Interface.Id

Write-Host "Added AzureVMNetworkInterface successfully"

$VirtualMachine = Set-AzureRmVMOSDisk -VM $VirtualMachine -Name $OSDiskName -VhdUri $OSDiskUri -CreateOption FromImage

Write-Host "Created AzureVMOSDisk successfully"

if ($SshPubKey)
{
    $VirtualMachine = Add-AzureRmVMSshPublicKey -VM $VirtualMachine -KeyData $SshPubKey -Path ("/home/" + $Username + "/.ssh/authorized_keys")

    Write-Host "Added SSH public key successfully"
}

## Create the VM in Azure
New-AzureRmVM -ResourceGroupName $ResourceGroupName -Location $Location -VM $VirtualMachine

Write-Host "Created AzureVM successfully: $VMName"

$VirtualMachine = Get-AzureRmVM -ResourceGroupName $ResourceGroupName -Name $VMName

Write-Host "Fetched VM successfully"

Add-AzureRmVMDataDisk -VM $VirtualMachine -Name $DataDisk1Name -Caching None -DiskSizeInGB 10 -Lun 0 -VhdUri $DataDisk1Uri -CreateOption Empty
Add-AzureRmVMDataDisk -VM $VirtualMachine -Name $DataDisk2Name -Caching None -DiskSizeInGB 10 -Lun 1 -VhdUri $DataDisk2Uri -CreateOption Empty

Write-Host "Added DataDisks successfully: $DataDisk1Name, $DataDisk2Name"

Update-AzureRmVM -ResourceGroupName $ResourceGroupName -VM $VirtualMachine

Write-Host "Updated VM successfully"

## SSH preparation

if ($SshPrivKeyPath)
{
    $global:Hostname = $PublicIp.DnsSettings.Fqdn.ToString()
    $commandFileName = $ResourcePrefix + "Commands.txt"

    $commands = @"
sudo mkdir /root/.ssh
sudo cp .ssh/authorized_keys /root/.ssh/
sudo chmod 700 /root/.ssh
sudo chmod 600 /root/.ssh/authorized_keys 
sudo restorecon -R -v /root/.ssh
sudo echo "PermitRootLogin yes" >>/etc/ssh/sshd_config
sudo service sshd restart
exit
"@

    $commands | Out-File -Encoding ascii $commandFileName
    dos2unix $commandFileName
    cmd /c "ssh -tt -o UserKnownHostsFile=C:\Windows\System32\NUL -o StrictHostKeyChecking=no -i $SshPrivKeyPath ${Username}@${Hostname} <$commandFileName"
    Remove-Item $commandFileName

    Write-Host "Copied SSH public key for root"

    $commands = @"
(cat <<EOF
alias adetail='tail -f /var/log/azure/Microsoft.Azure.Security.A*D*E*ForLinux*/*/extension.log'
alias adecat='cat /var/log/azure/Microsoft.Azure.Security.A*D*E*ForLinux*/*/extension.log'
EOF
) >> /root/.bashrc

apt-get install -yq mdadm
yum install -y mdadm
exit
"@

    $commands | Out-File -Encoding ascii $commandFileName
    dos2unix $commandFileName
    cmd /c "ssh -o UserKnownHostsFile=C:\Windows\System32\NUL -o StrictHostKeyChecking=no -i $SshPrivKeyPath root@${Hostname} <$commandFileName"
    Remove-Item $commandFileName

    Write-Host "Installed mdadm"

    $commands = @"
mdadm --create --verbose /dev/md0 --level=0 --raid-devices=2 /dev/sdc /dev/sdd
mkdir -p /etc/mdadm
mdadm --detail --scan > /etc/mdadm/mdadm.conf
exit
"@

    $commands | Out-File -Encoding ascii $commandFileName
    dos2unix $commandFileName
    cmd /c "ssh -o UserKnownHostsFile=C:\Windows\System32\NUL -o StrictHostKeyChecking=no -i $SshPrivKeyPath root@${Hostname} <$commandFileName"
    Remove-Item $commandFileName

    Write-Host "Created RAID array"

    $commands = @"
sed -i 's/SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
reboot
"@

    $commands | Out-File -Encoding ascii $commandFileName
    dos2unix $commandFileName
    cmd /c "ssh -o UserKnownHostsFile=C:\Windows\System32\NUL -o StrictHostKeyChecking=no -i $SshPrivKeyPath root@${Hostname} <$commandFileName"
    Remove-Item $commandFileName

    Start-Sleep 5

    $vmRunning = $false

    while(!$vmRunning)
    {
        try
        {
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.Connect($Hostname, "22")
            $vmRunning = $true
        }
        catch
        {
            Write-Host "VM is not up yet"
        }
    }

    Write-Host "SELinux disabled"

    $commands = @"
lsblk
exit
"@

    $commands | Out-File -Encoding ascii $commandFileName
    dos2unix $commandFileName
    $stdout = cmd /c "ssh -o UserKnownHostsFile=C:\Windows\System32\NUL -o StrictHostKeyChecking=no -i $SshPrivKeyPath root@${Hostname} <$commandFileName"
    Remove-Item $commandFileName

    $global:RaidBlockDevice = "/dev/" + [regex]::Match($stdout, '(md\d+)').Captures.Groups[0].Value

    Write-Host "Encrypting RAID device: $RaidBlockDevice"
}

## Encryption

Read-Host "Press Enter to continue..."

$global:Settings = @{
    "AADClientID" = $AadClientId;
    "DiskFormatQuery" = "[{`"dev_path`":`"$RaidBlockDevice`",`"file_system`":`"ext4`",`"name`":`"encryptedraid`"}]";
    "EncryptionOperation" = "EnableEncryptionFormat";
    "KeyEncryptionAlgorithm" = "RSA-OAEP";
    "KeyEncryptionKeyURL" = $KeyEncryptionKey.Id;
    "KeyVaultURL" = $KeyVault.VaultUri;
    "SequenceVersion" = "1";
    "VolumeType" = $VolumeType;
}

$global:ProtectedSettings = @{
    "AADClientSecret" = $AadClientSecret;
}

Set-AzureRmVMExtension `
    -ResourceGroupName $ResourceGroupName `
    -Location $Location `
    -VMName $VMName `
    -Name $ExtensionName `
    -Publisher "Microsoft.Azure.Security" `
    -Type "AzureDiskEncryptionForLinux" `
    -TypeHandlerVersion "0.1" `
    -Settings $Settings `
    -ProtectedSettings $ProtectedSettings

Write-Host "Set AzureRmVMExtension successfully"

$VirtualMachine = Get-AzureRmVM -ResourceGroupName $ResourceGroupName -Name $VMName
$global:InstanceView = Get-AzureRmVM -ResourceGroupName $ResourceGroupName -Name $VMName -Status

$KVSecretRef = New-Object Microsoft.Azure.Management.Compute.Models.KeyVaultSecretReference -ArgumentList @($InstanceView.Extensions[0].Statuses[0].Message, $KeyVault.ResourceId)
$KVKeyRef = New-Object Microsoft.Azure.Management.Compute.Models.KeyVaultKeyReference -ArgumentList @($KeyEncryptionKey.Id, $KeyVault.ResourceId)
$VirtualMachine.StorageProfile.OsDisk.EncryptionSettings = New-Object Microsoft.Azure.Management.Compute.Models.DiskEncryptionSettings -ArgumentList @($KVSecretRef, $KVKeyRef, $true)

Update-AzureRmVM -ResourceGroupName $ResourceGroupName -VM $VirtualMachine

Write-Host "Updated VM successfully"
