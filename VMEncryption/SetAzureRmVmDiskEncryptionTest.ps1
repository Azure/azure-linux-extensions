Param(
    [Parameter(Mandatory=$true)]
	[string] $SubscriptionId,
    [Parameter(Mandatory=$true)]
	[string] $AadClientId,
    [Parameter(Mandatory=$true)]
	[string] $AadClientSecret,
    [Parameter(Mandatory=$true)]
	[string] $ResourcePrefix,
    [string] $Location="eastus"
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

Add-AzureKeyVaultKey -VaultName $KeyVaultName -Name "diskencryptionkey" -Destination Software

Write-Host "Added AzureRmKeyVaultKey successfully"

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
$global:VMSize = "Standard_D2"
$global:OSDiskName = $VMName + "OsDisk"
$global:OSDiskUri = $StorageAccount.PrimaryEndpoints.Blob.ToString() + "vhds/" + $OSDiskName + ".vhd"
$global:DataDiskName = $VMName + "DataDisk"
$global:DataDiskUri = $StorageAccount.PrimaryEndpoints.Blob.ToString() + "vhds/" + $DataDiskName + ".vhd"

## Setup local VM object
$global:Credential = Get-Credential

Write-Host "Fetched credentials successfully"

$global:VirtualMachine = New-AzureRmVMConfig -VMName $VMName -VMSize $VMSize

Write-Host "Created AzureRmVMConfig successfully"

$VirtualMachine = Set-AzureRmVMOperatingSystem -VM $VirtualMachine -Linux -ComputerName $ComputerName -Credential $Credential

Write-Host "Set AzureRmVMOperatingSystem successfully"

$VirtualMachine = Set-AzureRmVMSourceImage -VM $VirtualMachine -PublisherName "Canonical" -Offer "UbuntuServer" -Skus "14.04.4-DAILY-LTS" -Version "latest"

Write-Host "Set AzureVMSourceImage successfully"

$VirtualMachine = Add-AzureRmVMNetworkInterface -VM $VirtualMachine -Id $Interface.Id

Write-Host "Added AzureVMNetworkInterface successfully"

$VirtualMachine = Set-AzureRmVMOSDisk -VM $VirtualMachine -Name $OSDiskName -VhdUri $OSDiskUri -CreateOption FromImage

Write-Host "Created AzureVMOSDisk successfully"

## Create the VM in Azure
New-AzureRmVM -ResourceGroupName $ResourceGroupName -Location $Location -VM $VirtualMachine

Write-Host "Created AzureVM successfully: $VMName"

$VirtualMachine = Get-AzureRmVM -ResourceGroupName $ResourceGroupName -Name $VMName

Write-Host "Fetched VM successfully"

Add-AzureRmVMDataDisk -VM $VirtualMachine -Name $DataDiskName -Caching None -DiskSizeInGB 1 -Lun 0 -VhdUri $DataDiskUri -CreateOption Empty

Write-Host "Added DataDisk successfully: $DataDiskName"

Update-AzureRmVM -ResourceGroupName $ResourceGroupName -VM $VirtualMachine

Write-Host "Updated VM successfully"

## Encryption

Read-Host "Press Enter to continue..."
Read-Host "Press Enter to continue..."
Read-Host "Press Enter to continue..."

$global:DiskEncryptionKey = Get-AzureKeyVaultKey -VaultName $KeyVault.OriginalVault.Name -Name "diskencryptionkey"

Write-Host "Fetched DiskEncryptionKey successfully"

Set-AzureRmVMDiskEncryptionExtension `
    -ResourceGroupName $ResourceGroupName `
    -VMName $VMName `
    -AadClientID $AadClientId `
    -AadClientSecret $AadClientSecret `
    -DiskEncryptionKeyVaultId $KeyVault.ResourceId `
    -DiskEncryptionKeyVaultUrl $KeyVault.VaultUri `
    -KeyEncryptionKeyVaultId $KeyVault.ResourceId `
    -KeyEncryptionKeyURL $DiskEncryptionKey.Id `
    -KeyEncryptionAlgorithm "RSA-OAEP" `
    -VolumeType "Data" `
    -SequenceVersion "1"

Write-Host "Set AzureRmVMDiskEncryptionExtension successfully"

