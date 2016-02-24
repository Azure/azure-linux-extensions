#scp -r main root@fareast-andliu.cloudapp.net:/var/lib/waagent/Microsoft.OSTCExtensions.VMEncryption-0.1/main

function Encrypt-Disk
{
	param
	(
		[string]$cloudServiceName,
		[string]$virtualMachineName
	)
    $vm = (Get-AzureVM -ServiceName $cloudServiceName -Name $virtualMachineName)


    $publicConfig='
    {
        "command":"enableencryption_clone",
        "query":[{"source_scsi_number":"[5:0:0:0]","target_scsi_number":"[5:0:0:1]"},{"source_scsi_number":"[5:0:0:2]","target_scsi_number":"[5:0:0:3]"}],
        "filesystem":"ext4",
        "mountpoint":"/mnt/",
        "KeyEncryptionKeyURL":"https://andliukeyvault.vault.azure.net/keys/mykey",
        "KeyVaultURL":"https://andliukeyvault.vault.azure.net/",
        "AADClientID":"b7b48143-6c58-4cd4-a9e0-0a15cbda0614",
        "KeyEncryptionAlgorithm":"RSA1_5",
        "BitlockerVolumeType":"Data"
    }'

    $privateConfig='
    {
        "AADClientSecret":"[secret]"
    }
    '
    $tempAzurevm = (Get-AzureVM -ServiceName $cloudServiceName -Name $virtualMachineName)
 
    set-azurevmextension -extensionName "VMEncryption" -Publisher "Microsoft.OSTCExtensions" -Version 0.1 -vm $tempAzurevm -PrivateConfiguration $privateConfig -PublicConfiguration $publicConfig | update-azurevm
}


Add-AzureAccount
Select-AzureSubscription "CRP TiP Sub 001"
Encrypt-Disk -cloudServiceName "andliu-ubuntu14" -virtualMachineName "andliu-ubuntu14"
