Add-AzureRmAccount 
Set-AzureRmContext -SubscriptionName "OSTC Shanghai Dev"
$RGName = 'andliu-northus'
$VmName = 'andliu-sles12'
$Location = 'North Central US'

$ExtensionName = 'RDMAUpdateForLinux'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = "0.1"

$PublicConf = '{}'
$PrivateConf = '{}'

Set-AzureRmVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher -ExtensionType $ExtensionName `
  -TypeHandlerVersion $Version -Settingstring $PublicConf -ProtectedSettingString $PrivateConf

