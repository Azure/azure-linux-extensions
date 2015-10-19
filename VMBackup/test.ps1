
Select-AzureSubscription -Current "OSTC Shanghai Dev"


# object str in the public config is the backup meta data
$publicConfig='
{
        "locale":"en-us",
        "taskId":"9e136e10-fb80-4467-891e-994965100000",
        "logsBlobUri":"https://andliu.blob.core.windows.net/blobs/a.txt?sv=2013-08-15&sr=b&sig=f7qZU7ZxDcUDc0l3kcdnF0vqFJDC5gz6LdiJhC3xRxg%3D&st=2015-10-09T07%3A06%3A56Z&se=2015-10-10T07%3A06%3A56Z&sp=rwdl",
        "statusBlobUri":"https://andliu.blob.core.windows.net/blobs/b.txt?sv=2013-08-15&sr=b&sig=Hliw04gkzsG65l%2FnCAhXJ0CViSaEzkTpfuwSq35AYlk%3D&st=2015-10-09T07%3A07%3A17Z&se=2015-10-10T07%3A07%3A17Z&sp=rwdl",
        "commandStartTimeUTCTicks":635798983509961452,
        "commandToExecute":"snapshot",
        "objectStr":"CiAgICAgICAgICAgICAgICB7CiAgICAgICAgImJhY2t1cE1ldGFkYXRhIjpbCiAgICAgICAgewogICAgICAgICJLZXkiOiJrZXkxIiwiVmFsdWUiOiJ2YWx1ZTEiCiAgICAgICAgfSwKICAgICAgICB7CiAgICAgICAgIktleSI6ImtleTIiLCJWYWx1ZSI6InZhbHVlMiIKICAgICAgICB9XQogICAgICAgIH0KICAgICAgICA="
}
'
# objectStr in the private config is the sas uri of the blobs.
$privateconfig='
{
"objectStr":"CiAgICAgICAgewoiYmxvYlNBU1VyaSI6WwoiaHR0cHM6Ly9hbmRsaXUuYmxvYi5jb3JlLndpbmRvd3MubmV0L2V4dGVuc2lvbnMvYS56aXA/c3Y9MjAxNC0wMi0xNCZzcj1jJnNpZz02dFhBbzFPNzFYYlp6Q3FMUW8weDZJTlpISHk3TjVxTzg5QmM3TyUyRll2TUUlM0Qmc3Q9MjAxNS0wMS0yMlQxNiUzQTAwJTNBMDBaJnNlPTIwMTktMDEtMzBUMTYlM0EwMCUzQTAwWiZzcD1yd2RsIl0KfQogICAgICAgIA=="
}
'
$servicename="andliu-ubunt1"
$tempAzurevm = (Get-AzureVM -ServiceName $servicename)

set-azurevmextension -extensionName "AgentBackupLinuxExtension2" -Publisher "Microsoft.OSTCExtensions" -Version 1.0 -vm $tempAzurevm -PublicConfiguration $publicConfig -PrivateConfiguration $privateconfig | update-azurevm