#!/bin/bash

# A shell script utility to decrypt the extension's protected settings for debugging purpose
# Must be run at /var/lib/waagent/Microsoft.Azure.Diagnostics.LinuxDiagnostic-.../
# with the settings file path (e.g., config/0.settings) as the only cmdline arg

if [ $# -lt 1 ]; then
    echo "Usage: $0 <ext_settings_file_path>"
    exit 1
fi

thumbprint=$(jq -r '.runtimeSettings[].handlerSettings.protectedSettingsCertThumbprint' $1)
jq -r '.runtimeSettings[].handlerSettings.protectedSettings' $1 | base64 --decode | openssl smime -inform DER -decrypt -recip ../$thumbprint.crt -inkey ../$thumbprint.prv | jq .
