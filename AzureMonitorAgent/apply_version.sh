#! /bin/bash

source ./agent.version

echo "AGENT_VERSION=$AGENT_VERSION"
echo "MDSD_DEB_PACKAGE_NAME=$MDSD_DEB_PACKAGE_NAME"
echo "MDSD_RPM_PACKAGE_NAME=$MDSD_RPM_PACKAGE_NAME"


# updating HandlerManifest.json
# check for "version": "x.x.x",
sed -i "s/\"version\".*$/\"version\": \"$AGENT_VERSION\",/g" HandlerManifest.json

# updating agent.py
sed -i "s/^BundleFileNameDeb = .*$/BundleFileNameDeb = '$MDSD_DEB_PACKAGE_NAME'/" agent.py
sed -i "s/^BundleFileNameRpm = .*$/BundleFileNameRpm = '$MDSD_RPM_PACKAGE_NAME'/" agent.py

sed -i "s/AMA_VERSION/$AGENT_VERSION/" services/metrics-extension-otlp.service
sed -i "s/AMA_VERSION/$AGENT_VERSION/" services/metrics-extension-cmv2.service

# updating manifest.xml
# check <Version>...</Version>
sed -i -e "s|<Version>[0-9a-z.]\{1,\}</Version>|<Version>$AGENT_VERSION</Version>|g" manifest.xml
