Add-AzureRmAccount 
Set-AzureRmContext -SubscriptionName "OSTC Shanghai Dev"
$RGName = 'andliuresourcegroup2'
$VmName = 'andliu-sles'
$Location = 'North Central US'

$ExtensionName = 'RDMAUpdate'
$Publisher = 'Microsoft.OSTCExtensions'
$Version = "0.1"

$PublicConf = '{}'
$PrivateConf = '{}'

Set-AzureRmVMExtension -ResourceGroupName $RGName -VMName $VmName -Location $Location `
  -Name $ExtensionName -Publisher $Publisher -ExtensionType $ExtensionName `
  -TypeHandlerVersion $Version -Settingstring $PublicConf -ProtectedSettingString $PrivateConf





    {
  "type": "Microsoft.Compute/virtualMachines/extensions",
  "name": "RDMAUpdate",
  "apiVersion": "<api-version>",
  "location": "North Central US",
  "dependsOn": [
    "[concat('Microsoft.Compute/virtualMachines/', <vm-name>)]"
  ],
  "properties": {
    "publisher": "Microsoft.OSTCExtensions",
    "type": "VMAccessForLinux",
    "typeHandlerVersion": "1.1",
    "settings": {},
    "protectedSettings": {
      "username": "<username>",
      "password": "<password>",
      "reset_ssh": true,
      "ssh_key": "<ssh-key>",
      "remove_user": "<username-to-remove>"
    }
  }

}