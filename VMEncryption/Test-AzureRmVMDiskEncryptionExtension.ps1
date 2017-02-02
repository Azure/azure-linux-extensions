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
    [string] $VMSize="Standard_D2",
    [switch] $DryRun=$false,
    [switch] $Force=$false
)

$ErrorActionPreference = "Stop"

Set-AzureRmContext -SubscriptionId $SubscriptionId

Write-Host "Set AzureRmContext successfully"

## Resource Group
$global:ResourceGroupName = $ResourcePrefix + "ResourceGroup"

if(!$DryRun)
{
    New-AzureRmResourceGroup -Name $ResourceGroupName -Location $Location
}

Write-Host "Created ResourceGroup successfully: $ResourceGroupName"

## KeyVault
$global:KeyVaultName = $ResourcePrefix + "KeyVault"

if(!$DryRun)
{
    $global:KeyVault = New-AzureRmKeyVault -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName -Location $Location
}
else
{
    $global:KeyVault = Get-AzureRmKeyVault -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName
}

Write-Host "Created KeyVault successfully: $KeyVaultName"

if(!$DryRun)
{
    Set-AzureRmKeyVaultAccessPolicy -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName -ServicePrincipalName $AadClientId -PermissionsToKeys all -PermissionsToSecrets all
    Set-AzureRmKeyVaultAccessPolicy -VaultName $KeyVaultName -ResourceGroupName $ResourceGroupName -EnabledForDiskEncryption
}

Write-Host "Set AzureRmKeyVaultAccessPolicy successfully"

if(!$DryRun)
{
    Add-AzureKeyVaultKey -VaultName $KeyVaultName -Name "keyencryptionkey" -Destination Software
}

Write-Host "Added AzureRmKeyVaultKey successfully"

$global:KeyEncryptionKey = Get-AzureKeyVaultKey -VaultName $KeyVault.OriginalVault.Name -Name "keyencryptionkey"

Write-Host "Fetched KeyEncryptionKey successfully"

## Storage
$global:StorageName = ($ResourcePrefix + "Storage").ToLower()
$global:StorageType = "Standard_GRS"
$global:ContainerName = "vhds"

if(!$DryRun)
{
    $global:StorageAccount = New-AzureRmStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageName -Type $StorageType -Location $Location
}
else
{
    $global:StorageAccount = Get-AzureRmStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageName
}

Write-Host "Created StorageAccount successfully: $StorageName"

## Network
$global:PublicIpName = $ResourcePrefix + "PublicIp"
$global:InterfaceName = $ResourcePrefix + "NetworkInterface"
$global:SubnetName = $ResourcePrefix + "Subnet"
$global:VNetName = $ResourcePrefix + "VNet"
$global:VNetAddressPrefix = "10.0.0.0/16"
$global:VNetSubnetAddressPrefix = "10.0.0.0/24"
$global:DomainNameLabel = ($ResourcePrefix + "VM").ToLower()

if(!$DryRun)
{
    $global:PublicIp = New-AzureRmPublicIpAddress -Name $PublicIpName -ResourceGroupName $ResourceGroupName -Location $Location -AllocationMethod Dynamic -DomainNameLabel $DomainNameLabel
}
else
{
    $global:PublicIp = Get-AzureRmPublicIpAddress -Name $PublicIpName -ResourceGroupName $ResourceGroupName
}

Write-Host "Created PublicIp successfully: " $PublicIp.DnsSettings.Fqdn.ToString()

if(!$DryRun)
{
    $global:SubnetConfig = New-AzureRmVirtualNetworkSubnetConfig -Name $SubnetName -AddressPrefix $VNetSubnetAddressPrefix
}

Write-Host "Created SubnetConfig successfully: $SubnetName"

if(!$DryRun)
{
    $global:VNet = New-AzureRmVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroupName -Location $Location -AddressPrefix $VNetAddressPrefix -Subnet $SubnetConfig
}
else
{
    $global:VNet = Get-AzureRmVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroupName
    $global:SubnetConfig = Get-AzureRmVirtualNetworkSubnetConfig -Name $SubnetName -VirtualNetwork $VNet
}

Write-Host "Created AzureRmVirtualNetwork successfully: $VNetName"

if(!$DryRun)
{
    $global:Interface = New-AzureRmNetworkInterface -Name $InterfaceName -ResourceGroupName $ResourceGroupName -Location $Location -SubnetId $VNet.Subnets[0].Id -PublicIpAddressId $PublicIp.Id
}
else
{
    $global:Interface = Get-AzureRmNetworkInterface -Name $InterfaceName -ResourceGroupName $ResourceGroupName
}

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
if(!$DryRun)
{
    New-AzureRmVM -ResourceGroupName $ResourceGroupName -Location $Location -VM $VirtualMachine
}

Write-Host "Created AzureVM successfully: $VMName"

$VirtualMachine = Get-AzureRmVM -ResourceGroupName $ResourceGroupName -Name $VMName

Write-Host "Fetched VM successfully"

if(!$DryRun)
{
    Add-AzureRmVMDataDisk -VM $VirtualMachine -Name $DataDisk1Name -Caching None -DiskSizeInGB 1 -Lun 0 -VhdUri $DataDisk1Uri -CreateOption Empty
    Add-AzureRmVMDataDisk -VM $VirtualMachine -Name $DataDisk2Name -Caching None -DiskSizeInGB 1 -Lun 1 -VhdUri $DataDisk2Uri -CreateOption Empty
}

Write-Host "Added DataDisks successfully: $DataDisk1Name, $DataDisk2Name"

if(!$DryRun)
{
    Update-AzureRmVM -ResourceGroupName $ResourceGroupName -VM $VirtualMachine
}

Write-Host "Updated VM successfully"

## SSH preparation

$global:Hostname = $PublicIp.DnsSettings.Fqdn.ToString()

if ($SshPrivKeyPath -and !$DryRun)
{
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

parted /dev/sdc
mklabel msdos
mkpart pri ext2 0% 100%
quit

parted /dev/sdd
mklabel msdos
mkpart pri ext2 0% 100%
quit

mkfs.ext4 /dev/sdc1
mkfs.ext4 /dev/sdd1

UUID1="`$(blkid -s UUID -o value /dev/sdc1)"
UUID2="`$(blkid -s UUID -o value /dev/sdd1)"

echo "UUID=`$UUID1 /data1 ext4 defaults 0 0" >>/etc/fstab
echo "UUID=`$UUID2 /data2 ext4 defaults 0 0" >>/etc/fstab

mkdir /data1
mkdir /data2

mount -a
exit
"@

    $commands | Out-File -Encoding ascii $commandFileName
    dos2unix $commandFileName
    cmd /c "ssh -o UserKnownHostsFile=C:\Windows\System32\NUL -o StrictHostKeyChecking=no -i $SshPrivKeyPath root@${Hostname} <$commandFileName"
    Remove-Item $commandFileName

    Write-Host "Mounted data partitions"

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
}

## Encryption

if(!$DryRun)
{
    $global:EncryptionEnableOutput = Set-AzureRmVMDiskEncryptionExtension `
        -ExtensionName $ExtensionName `
        -ResourceGroupName $ResourceGroupName `
        -VMName $VMName `
        -AadClientID $AadClientId `
        -AadClientSecret $AadClientSecret `
        -DiskEncryptionKeyVaultId $KeyVault.ResourceId `
        -DiskEncryptionKeyVaultUrl $KeyVault.VaultUri `
        -KeyEncryptionKeyVaultId $KeyVault.ResourceId `
        -KeyEncryptionKeyURL $KeyEncryptionKey.Id `
        -KeyEncryptionAlgorithm "RSA-OAEP" `
        -VolumeType $VolumeType `
        -SequenceVersion "1" `
        -Force:$Force 3>&1 | Out-String

    Write-Host "Set AzureRmVMDiskEncryptionExtension successfully"

    $global:BackupTag = [regex]::match($EncryptionEnableOutput, '(AzureEnc.*?),').Groups[1].Value
}
