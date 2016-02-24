function Create-Key-Disk
{
	param
	(
		[string]$cloudServiceName,
		[string]$virtualMachineName,
        [string]$localFile
	)
    
    $vm = (Get-AzureVM -ServiceName $cloudServiceName -Name $virtualMachineName)

    $osDisk = $vm | Get-AzureOSDisk 
    $osDiskMediaLink = $osDisk.MediaLink
    $diskName="fat32_"+[guid]::NewGuid().ToString()
    $destinationKeyDiskPath = $osDiskMediaLink.Scheme+"://"+$osDiskMediaLink.Host+$osDiskMediaLink.Segments[0]+$osDiskMediaLink.Segments[1]+$diskName+".vhd"
    #prepare the keydisk

    $dataDisks = $vm | Get-AzureDataDisk
    $lun = -1
    Foreach($disk in $dataDisks)
    {
        if($disk.lun -gt $lun)
        {
            $lun=$disk.lun
        }
    }
    $lun+=1

    Add-AzureVhd -Destination $destinationKeyDiskPath -LocalFilePath $localFile

    Add-AzureDisk -MediaLocation $destinationKeyDiskPath -DiskName $diskName -Label "keydisklabel$lun"

    Add-AzureDataDisk -Import -DiskName $diskName -LUN $lun -VM $vm | update-azurevm
}

Add-AzureAccount
Select-AzureSubscription "CRP TiP Sub 001"
Create-Key-Disk -cloudServiceName "fareast-andliu" -virtualMachineName "fareast-andliu" -localFile "d:\fat32key.vhd"
