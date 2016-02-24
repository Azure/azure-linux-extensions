#scp -r main root@fareast-andliu.cloudapp.net:/var/lib/waagent/Microsoft.OSTCExtensions.VMEncryption-0.1/main

function Encrypt-Disk
{
    param
    (
        [string]$cloudServiceName,
        [string]$virtualMachineName
    )
    $vm = (Get-AzureVM -ServiceName $cloudServiceName -Name $virtualMachineName)

    $osDisk = $vm | Get-AzureOSDisk 
    $osDiskMediaLink = $osDisk.MediaLink
    $destinationKeyDiskPath = $osDiskMediaLink.Scheme+"://"+$osDiskMediaLink.Host+$osDiskMediaLink.Segments[0]+$osDiskMediaLink.Segments[1]+"empty_disk_blob"+[guid]::NewGuid().ToString()+".vhd"
    #prepare the keydisk

    # get the max lun of the vm
    #$dataDisks = $vm | Get-AzureDataDisk
    # $lun = -1
    # Foreach($disk in $dataDisks)
    # {
    #    if($disk.lun -gt $lun)
    #    {
    #        $lun=$disk.lun
    #    }
    #}
    #$lun+=1
    #Write-Output "the lun of your newly attached disk is "+$lun
    #Add-AzureDataDisk -CreateNew -DiskSizeInGB 3 -DiskLabel "disklabel$lun" -VM $vm -LUN $lun -MediaLocation $destinationKeyDiskPath| update-azurevm

    $publicConfig='
    {
        "command":"enableencryption_format",
        "query":[{"source_scsi_number":"[5:0:0:2]","filesystem":"ext4","mount_point":"/mnt/"}],
        "KeyEncryptionKeyURL":"https://andliukeyvault.vault.azure.net/keys/mykey",
        "KeyVaultURL":"https://andliukeyvault.vault.azure.net/",
        "AADClientID":"b7b48143-6c58-4cd4-a9e0-0a15cbda0614",
        "KeyEncryptionAlgorithm":"RSA1_5",
        "BitlockerVolumeType":"Data"
    }
    '
    $privateConfig='
    {
        "AADClientSecret":"[secret]"
    }
    '

    #construct the parameters

    $tempAzurevm = (Get-AzureVM -ServiceName $cloudServiceName -Name $virtualMachineName)
 
    set-azurevmextension -extensionName "VMEncryption" -Publisher "Microsoft.OSTCExtensions" -Version 0.1 -vm $tempAzurevm -PrivateConfiguration $privateConfig -PublicConfiguration $publicConfig | update-azurevm
}

#Add-AzureAccount
Select-AzureSubscription "CRP TiP Sub 001"
Encrypt-Disk -cloudServiceName "andliu-ubuntu14" -virtualMachineName "andliu-ubuntu14"
