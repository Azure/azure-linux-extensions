#scp -r main root@fareast-andliu.cloudapp.net:/var/lib/waagent/Microsoft.OSTCExtensions.VMEncryption-0.1/main


#Add-AzureAccount
#Select-AzureSubscription "OSTC Shanghai Dev"
Add-AzureRmAccount 
Set-AzureRmContext -SubscriptionName "OSTC Shanghai Dev"

$resourceGroupName="andliu-eastasia"
$vmName="andliu-ubuntu"
$aadClientId="b7b48143-6c58-4cd4-a9e0-0a15cbda0614"
$aadClientSecret="[secret]"
$keyVaultUrl="https://andliukeyvault.vault.azure.net/"
#$location="North Central US"
$diskEncryptionKeyVaultId="/subscriptions/c4528d9e-c99a-48bb-b12d-fde2176a43b8/resourceGroups/andliu-eastasia/providers/Microsoft.KeyVault/vaults/andliukeyvault"
$keyEncryptionKeyVaultId="/subscriptions/c4528d9e-c99a-48bb-b12d-fde2176a43b8/resourceGroups/andliu-eastasia/providers/Microsoft.KeyVault/vaults/andliukeyvaul"
$keyEncryptionKeyUrl=$null
$keyEncryptionAlgorithm="RSA-OAEP"
$volumeType="Data"
$extensionName="andliu-ubuntu"
$sequenceVersion = "1"

#"command":"enableencryption_all_inplace",
#"KeyEncryptionKeyURL":"https://andliukeyvault.vault.azure.net/keys/mykey",
#        "KeyVaultURL":"https://andliukeyvault.vault.azure.net/",
#        "AADClientID":"b7b48143-6c58-4cd4-a9e0-0a15cbda0614",
#        "KeyEncryptionAlgorithm":"RSA1_5",
#        "BitlockerVolumeType":"Data"


Set-AzureRmVMDiskEncryptionExtension -ResourceGroupName $resourceGroupName -VMName $vmName -AadClientID $aadClientId -AadClientSecret $aadClientSecret -DiskEncryptionKeyVaultUrl $keyVaultUrl -DiskEncryptionKeyVaultId $diskEncryptionKeyVaultId -KeyEncryptionKeyVaultId $keyEncryptionKeyVaultId -KeyEncryptionAlgorithm $keyEncryptionAlgorithm -VolumeType $volumeType -Name $extensionName -SequenceVersion $sequenceVersion


azure vm enable-disk-encryption -g andliuresourcegroup2 -n andliu-encrypt6 -a b7b48143-6c58-4cd4-a9e0-0a15cbda0614 -p [secret] -k https://andliukeyvault.vault.azure.net -r /subscriptions/c4528d9e-c99a-48bb-b12d-fde2176a43b8/resourceGroups/andliuresourcegroup2/providers/Microsoft.KeyVault/vaults/andliukeyvault -t Data -h "Password@123"