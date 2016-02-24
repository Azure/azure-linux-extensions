#scp -r main root@fareast-andliu.cloudapp.net:/var/lib/waagent/Microsoft.OSTCExtensions.VMEncryption-0.1/main


#Add-AzureAccount
Select-AzureRmSubscription "OSTC Shanghai Dev"

New-AzureRmKeyVault -VaultName "andliukeyvault" -ResourceGroupName "andliu-eastasia" -Location eastasia

Set-AzureRmKeyVaultAccessPolicy -VaultName andliukeyvault -ResourceGroupName andliu-eastasia -ServicePrincipalName b7b48143-6c58-4cd4-a9e0-0a15cbda0614 -PermissionsToKeys all -PermissionsToSecrets all

Add-AzureRmKeyVaultKey -VaultName "andliukeyvault" -Name "diskencryptionkey" -Destination Software

$ResourceGroupName = "diskencryptiontst"
$Location = "westus"

## Storage
$StorageName = "andliuencrypt"
$StorageType = "Standard_GRS"

## Network
$InterfaceName = "andliuencryptifn"
$Subnet1Name = "Subnet1"
$VNetName = "VNet09"
$VNetAddressPrefix = "10.0.0.0/16"
$VNetSubnetAddressPrefix = "10.0.0.0/24"

## Compute
$VMName = "ubuntu-encrypt"
$ComputerName = "Server22"
$VMSize = "Standard_A2"
$OSDiskName = $VMName + "osDisk"

# Resource Group
New-AzureResourceGroup -Name $ResourceGroupName -Location $Location

# Storage
$StorageAccount = New-AzureStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageName -Type $StorageType -Location $Location

# Network
$PIp = New-AzurePublicIpAddress -Name $InterfaceName -ResourceGroupName $ResourceGroupName -Location $Location -AllocationMethod Dynamic
$SubnetConfig = New-AzureVirtualNetworkSubnetConfig -Name $Subnet1Name -AddressPrefix $VNetSubnetAddressPrefix
$VNet = New-AzureVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroupName -Location $Location -AddressPrefix $VNetAddressPrefix -Subnet $SubnetConfig
$Interface = New-AzureNetworkInterface -Name $InterfaceName -ResourceGroupName $ResourceGroupName -Location $Location -SubnetId $VNet.Subnets[0].Id -PublicIpAddressId $PIp.Id

# Compute

## Setup local VM object
$Credential = Get-Credential
$VirtualMachine = New-AzureVMConfig -VMName $VMName -VMSize $VMSize
$VirtualMachine = Set-AzureVMOperatingSystem -VM $VirtualMachine -Windows -ComputerName $ComputerName -Credential $Credential -ProvisionVMAgent -EnableAutoUpdate
$VirtualMachine = Set-AzureVMSourceImage -VM $VirtualMachine -PublisherName AzureRT.PIRCore.TestWAStage -Offer TestUbuntuServer -Skus 14.10 -Version "latest"
$VirtualMachine = Add-AzureVMNetworkInterface -VM $VirtualMachine -Id $Interface.Id
$OSDiskUri = $StorageAccount.PrimaryEndpoints.Blob.ToString() + "vhds/" + $OSDiskName + ".vhd"
$VirtualMachine = Set-AzureVMOSDisk -VM $VirtualMachine -Name $OSDiskName -VhdUri $OSDiskUri -CreateOption FromImage

## Create the VM in Azure
New-AzureVM -ResourceGroupName $ResourceGroupName -Location $Location -VM $VirtualMachine

New-AzureRmVMDiskEncryptionEnvironment -ResourceGroupName andliu-southeastasia -ApplicationDisplayName mydiskencryptionapp -ApplicationHomePage https://mydiskencryptionapp.onmicrosoft.com -IdentifierUris https://mydiskencryptionapp.onmicrosoft.com -AadClientSecret [secret] -KeyVaultName mydiskencryptionvault
#"command":"enableencryption_all_inplace",
#"KeyEncryptionKeyURL":"https://andliukeyvault.vault.azure.net/keys/mykey",
#        "KeyVaultURL":"https://andliukeyvault.vault.azure.net/",
#        "AADClientID":"b7b48143-6c58-4cd4-a9e0-0a15cbda0614",
#        "KeyEncryptionAlgorithm":"RSA1_5",
#        "BitlockerVolumeType":"Data"
Set-AzureDiskEncryptionExtension -ResourceGroupName "andliu-southeastasia" -Name "andliu-southeastasia" -Location "westus" -VMName "andliuencrypt" -AadClientID "b7b48143-6c58-4cd4-a9e0-0a15cbda0614" -AadClientSecret "[secret]" -KeyVaultURL "https://andliukeyvault.vault.azure.net/" -KeyEncryptionKeyURL "https://andliukeyvault.vault.azure.net/keys/mykey" -KeyEncryptionAlgorithm "RSA1_5" -VolumeType "Data" -Tag vmencryptiontag
