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

    $privateConfig='
    {
        "command":"enableencryption",
        "query":[{"source_scsi_number":"[5:0:0:0]","target_scsi_number":"[5:0:0:1]"}],
        "passphrase":"MicrosoftLoveLinuxBecausVeWeHaveCCIC@123"
    }
    '

    #construct the parameters

    $tempAzurevm = (Get-AzureVM -ServiceName $cloudServiceName -Name $virtualMachineName)
 
    set-azurevmextension -extensionName "VMEncryption2" -Publisher "Microsoft.OSTCExtensions" -Version 0.1 -vm $tempAzurevm -PrivateConfiguration $privateConfig | update-azurevm
}

#Add-AzureAccount
Select-AzureSubscription "CRP TiP Sub 001"
Encrypt-Disk -cloudServiceName "andliu-ubuntu14" -virtualMachineName "andliu-ubuntu14"
