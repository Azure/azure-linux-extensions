#!/bin/bash

#az login

cat <<EOF > ./restart_lad_cse.json
{
    "fileUris": [ "https://raw.githubusercontent.com/Azure/azure-linux-extensions/lad-2.3/Diagnostic/restart_lad/restart_lad_on_all_vms.sh" ],
    "commandToExecute": "./restart_lad_on_all_vms.sh"
}
EOF

subs=$(az account list --query [].id -o tsv)

for sub in $subs; do
    echo "=== On subscription: $sub"
    az account set -s $sub
    az vm list --query "[?storageProfile.osDisk.osType=='Linux'].[resourceGroup,name]" -o tsv | while read -r rg name; do
        echo "=== Recycling LAD on VM name: $name in resource group: $rg"
        az vm extension set --resource-group $rg --vm-name $name --name CustomScript --publisher Microsoft.Azure.Extensions --settings ./restart_lad_cse.json
    done
done
