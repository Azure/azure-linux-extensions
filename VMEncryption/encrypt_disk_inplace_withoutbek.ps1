#scp -r main root@fareast-andliu.cloudapp.net:/var/lib/waagent/Microsoft.OSTCExtensions.VMEncryption-0.1/main
. .\keyvault_prepare.ps1

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

    $publicConfig='
    {
        "command":"enableencryption_all_inplace",
        "KeyVaultURL":"https://andliukeyvault.vault.azure.net/",
        "AADClientID":"b7b48143-6c58-4cd4-a9e0-0a15cbda0614",
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
 
    set-azurevmextension -extensionName "VMEncryption" -Publisher "Microsoft.OSTCExtensions" -Version 0.1 -vm $tempAzurevm -PrivateConfiguration $privateConfig -PublicConfiguration $publicConfig| update-azurevm
}

#Add-AzureAccount
Select-AzureSubscription "CRP TiP Sub 001"
Encrypt-Disk -cloudServiceName "andliu-ubuntu14" -virtualMachineName "andliu-ubuntu14"
