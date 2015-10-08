$myCert = Get-Item Cert:\CurrentUser\My\db344174582e2194ae8173b69f02789a3f310968
#?$myCert = Get-Item Cert:\CurrentUser\My\24df021be04de1595918149726c88137660091ef
#Set-AzureSubscription -SubscriptionName "Free Trial" -Certificate $myCert -SubscriptionId 609b0e6f-e591-4a6a-bca3-07a1cceafb44
#Select-AzureSubscription -Current "OSTC Shanghai Test"

Set-AzureSubscription -SubscriptionName "OSTC Shanghai Test" -Certificate $myCert -SubscriptionId 4be8920b-2978-43d7-ab14-04d8549c1d05
Select-AzureSubscription -Current "OSTC Shanghai Test"

set-azuresubscription -subscriptionname "OSTC Shanghai Test" -CurrentStorageAccountName andliu
#0b11de9248dd4d87b18621318e037d37__RightImage-CentOS-6.5-x64-v14.1.3
#b39f27a8b8c64d52b05eac6a62ebad85__Ubuntu-14_04-LTS-amd64-server-20140724-en-us-30GB
#"0b11de9248dd4d87b18621318e037d37__RightImage-CentOS-6.5-x64-v14.1.3"
$imageName= "b39f27a8b8c64d52b05eac6a62ebad85__Ubuntu-14_04_1-LTS-amd64-server-20141125-en-us-30GB" #list all available images by get-azurevmimage
$servicename=(whoami).replace("\","-")+"vm"
$username="azureuser"
$password="Quattro!"
$affinitygroup="andliugroup"
Remove-AzureService -ServiceName $servicename -Force
New-AzureService -ServiceName $servicename -AffinityGroup $affinitygroup
New-AzureVM -ServiceName $servicename -VMs (( New-AzureVMConfig -Name $servicename -InstanceSize Small -ImageName $imageName | Add-AzureProvisioningConfig -Linux –LinuxUser $username -Password $password|  Set-AzureEndpoint -Name "SSH" -LocalPort "22" -PublicPort "22" -Protocol "tcp"  ))


# object str in the public config is the backup meta data
$publicConfig='
{
		"locale":"en-us",
		"taskId":"9e136e10-fb80-4467-891e-994965100000",
        "logsBlobUri":"https://andliu.blob.core.windows.net/extensions/log.txt?sv=2014-02-14&sr=c&sig=bNhD6gpp4JOTgOzDvzdO8HmqH%2BzuEjOWwdQf15gwcfg%3D&st=2014-11-09T16%3A00%3A00Z&se=2015-11-17T16%3A00%3A00Z&sp=rwdl",
        "statusBlobUri":"https://andliu.blob.core.windows.net/extensions/log.txt?sv=2014-02-14&sr=c&sig=bNhD6gpp4JOTgOzDvzdO8HmqH%2BzuEjOWwdQf15gwcfg%3D&st=2014-11-09T16%3A00%3A00Z&se=2015-11-17T16%3A00%3A00Z&sp=rwdl",
        "commandStartTimeUTCTicks":635798983509961452,
		"commandToExecute":"snapshot",
		"objectStr":"CiAgICAgICAgICAgICAgICB7CiAgICAgICAgImJhY2t1cE1ldGFkYXRhIjpbCiAgICAgICAgewogICAgICAgICJLZXkiOiJrZXkxIiwiVmFsdWUiOiJ2YWx1ZTEiCiAgICAgICAgfSwKICAgICAgICB7CiAgICAgICAgIktleSI6ImtleTIiLCJWYWx1ZSI6InZhbHVlMiIKICAgICAgICB9XQogICAgICAgIH0KICAgICAgICA="
}
'

#{"version":"1.0","timestampUTC":"2015-10-08T03:21:24Z",
#    "aggregateStatus":{
#    "guestAgentStatus":{"version":"WALinuxAgent-2.0.14","status":"Ready",
#    "formattedMessage":{"lang":"en-US","message":"GuestAgent is running and accepting new configurations."}},
#    "handlerAggregateStatus":[
#
#    {"status": "Ready", 
#    "runtimeSettingsStatus":  {"settingsStatus": {"status": {"status": "success", "formattedMessage": 
#    {"lang": "en-US", "message": "Enable SucceededEnable Succeeded with error: []"}, "operation": "Enable", "code": "1", "name": "Microsoft.Azure.RecoveryServices.VMSnapshotLinux"}, 
#    "timestampUTC": "2015-10-08T03:09:34Z"}, "sequenceNumber": "0"}, 
#    "handlerVersion": "1.0.3.0", 
#    "handlerName": "Microsoft.Azure.RecoveryServices.VMSnapshotLinux"}

#    ]}}

# objectStr in the private config is the sas uri of the blobs.
$privateconfig='
{
"objectStr":"CiAgICAgICAgewoiYmxvYlNBU1VyaSI6WwoiaHR0cHM6Ly9hbmRsaXUuYmxvYi5jb3JlLndpbmRvd3MubmV0L2V4dGVuc2lvbnMvYS56aXA/c3Y9MjAxNC0wMi0xNCZzcj1jJnNpZz02dFhBbzFPNzFYYlp6Q3FMUW8weDZJTlpISHk3TjVxTzg5QmM3TyUyRll2TUUlM0Qmc3Q9MjAxNS0wMS0yMlQxNiUzQTAwJTNBMDBaJnNlPTIwMTktMDEtMzBUMTYlM0EwMCUzQTAwWiZzcD1yd2RsIl0KfQogICAgICAgIA=="
}
'

$tempAzurevm = (Get-AzureVM -ServiceName $servicename)

set-azurevmextension -extensionName "AgentBackupLinuxExtension" -Publisher "Microsoft.OSTCExtensions" -Version 1.0 -vm $tempAzurevm -PublicConfiguration $publicConfig -PrivateConfiguration $privateconfig | update-azurevm