
Select-AzureSubscription -Current "OSTC Shanghai Dev"


# object str in the public config is the backup meta data
$publicConfig='
{
        "locale":"en-us",
        "taskId":"9e136e10-fb80-4467-891e-994965100000",
        "logsBlobUri":"https://andliu.blob.core.windows.net/blobs/a.txt?sv=2013-08-15&sr=b&sig=PuFBKd%2FMfPP92kL21973VGwUPloD5aeFZ24KEuVOvAs%3D&st=2015-10-19T09%3A23%3A55Z&se=2016-02-05T01%3A23%3A55Z&sp=rwdl",
        "statusBlobUri":"https://andliu.blob.core.windows.net/blobs/b.txt?sv=2013-08-15&sr=b&sig=PqsHA72pR8esXYz9%2B5bbBYJ%2B%2F4KRvV7Bic%2BGEhJxmS8%3D&st=2015-10-20T01%3A10%3A42Z&se=2016-07-14T17%3A10%3A42Z&sp=rwdl",
        "commandStartTimeUTCTicks":635809046306353843,
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