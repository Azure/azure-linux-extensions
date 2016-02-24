#scp -r main root@fareast-andliu.cloudapp.net:/var/lib/waagent/Microsoft.OSTCExtensions.VMEncryption-0.1/main


$passphrase="[secret]"
$encryption_keyvault_uri="https://andliukeyvault.vault.azure.net/keys/mykey"
$keyvault_uri="https://andliukeyvault.vault.azure.net/"
$AADClientID="b7b48143-6c58-4cd4-a9e0-0a15cbda0614"
$AADClientSecret="[secret]"
$alg_name="RSA1_5"
# passphrase, secret_keyvault_uri, encryption_keyvault_uri, AADClientID, alg_name, AADClientSecret
#Add-AzureAccount
#Select-AzureSubscription "CRP TiP Sub 001"
#Encrypt-Disk -cloudServiceName "andliu-ubuntu14" -virtualMachineName "andliu-ubuntu14"