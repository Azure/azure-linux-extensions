#! /bin/bash

source ./omsagent.version

echo "OMS_EXTENSION_VERSION=$OMS_EXTENSION_VERSION"
echo "OMS_SHELL_BUNDLE_VERSION=$OMS_SHELL_BUNDLE_VERSION"


# updating HandlerManifest.json
# check for "version": "1.12.5",
sed -i "s/\"version\".*$/\"version\": \"$OMS_EXTENSION_VERSION\",/g" HandlerManifest.json

# updating watcherutil.py
# check OMSExtensionVersion = '1.12.5'
sed -i "s/^OMSExtensionVersion = .*$/OMSExtensionVersion = '$OMS_EXTENSION_VERSION'/"  watcherutil.py

# updating omsagent.py
# check BundleFileName = 'omsagent-1.12.7-0.universal.x64.sh'
sed -i "s/^BundleFileName = .*$/BundleFileName = 'omsagent-$OMS_SHELL_BUNDLE_VERSION.universal.x64.sh'/" omsagent.py

# updating manifest.xml
# check <Version>...</Version>
sed -i -e "s|<Version>[0-9a-z.]\{1,\}</Version>|<Version>$OMS_EXTENSION_VERSION</Version>|g" manifest.xml