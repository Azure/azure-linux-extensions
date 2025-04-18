#! /bin/bash
set -e
source agent.version

usage()
{
    local basename=`basename $0`
    echo "usage: ./$basename <path to mdsd-<version>.{.deb, .rpm}> [path for zip output]"
}

input_path=$1
output_path=$2
PACKAGE_NAME="azuremonitor$AGENT_VERSION.zip"
if [[ "$1" == "--help" ]]; then
    usage
    exit 0
elif [[ ! -d $input_path ]]; then
    echo "DEB/RPM files path '$input_path' not found"
    usage
    exit 1
fi

if [[ "$output_path" == "" ]]; then
    output_path="../"
fi

# Packaging starts here
cp -r ../Utils .
cp ../Common/WALinuxAgent-2.0.16/waagent .

cp -r  ../LAD-AMA-Common/metrics_ext_utils .
cp -r  ../LAD-AMA-Common/telegraf_utils .
cp -f  ../Diagnostic/services/metrics-sourcer.service services/metrics-sourcer.service

# cleanup packages, ext
rm -rf packages MetricsExtensionBin amaCoreAgentBin KqlExtensionBin agentLauncherBin mdsdBin fluentBitBin tmp
mkdir -p packages MetricsExtensionBin amaCoreAgentBin KqlExtensionBin agentLauncherBin mdsdBin fluentBitBin

# copy shell bundle to packages/
cp $input_path/azuremonitoragent_$AGENT_VERSION* packages/
cp $input_path/azuremonitoragent-$AGENT_VERSION* packages/

# remove dynamic ssl packages
rm -f packages/*dynamicssl*

# validate HandlerManifest.json syntax
cat HandlerManifest.json | json_pp -f json -t null

mkdir -p tmp
cp $input_path/azuremonitoragent_$AGENT_VERSION*dynamicssl_x86_64.deb tmp/
AMA_DEB_PACKAGE_NAME=$(find tmp/ -type f -name "azuremonitoragent_*x86_64.deb" -printf "%f\\n" | head -n 1)
ar vx tmp/$AMA_DEB_PACKAGE_NAME --output=tmp
tar xvf tmp/data.tar.gz -C tmp
cp tmp/opt/microsoft/azuremonitoragent/bin/mdsd mdsdBin/mdsd_x86_64
cp tmp/opt/microsoft/azuremonitoragent/bin/mdsdmgr mdsdBin/mdsdmgr_x86_64
cp tmp/opt/microsoft/azuremonitoragent/bin/fluent-bit fluentBitBin/fluent-bit_x86_64
rm -rf tmp/

mkdir -p tmp
cp $input_path/azuremonitoragent_$AGENT_VERSION*dynamicssl_aarch64.deb tmp/
AMA_DEB_PACKAGE_NAME=$(find tmp/ -type f -name "azuremonitoragent_*aarch64.deb" -printf "%f\\n" | head -n 1)
ar vx tmp/$AMA_DEB_PACKAGE_NAME --output=tmp
tar xvf tmp/data.tar.gz -C tmp
cp tmp/opt/microsoft/azuremonitoragent/bin/mdsd mdsdBin/mdsd_aarch64
cp tmp/opt/microsoft/azuremonitoragent/bin/mdsdmgr mdsdBin/mdsdmgr_aarch64
cp tmp/opt/microsoft/azuremonitoragent/bin/fluent-bit fluentBitBin/fluent-bit_aarch64
rm -rf tmp/

cp $input_path/MetricsExtension* MetricsExtensionBin/
cp $input_path/x86_64/amacoreagent amaCoreAgentBin/amacoreagent_x86_64
cp -r $input_path/KqlExtension/* KqlExtensionBin/
cp $input_path/x86_64/liblz4x64.so amaCoreAgentBin/
cp $input_path/x86_64/libgrpc_csharp_ext.x64.so amaCoreAgentBin/
cp $input_path/x86_64/agentlauncher agentLauncherBin/agentlauncher_x86_64

# make the shim.sh file executable
chmod +x shim.sh

# sync the file copy
sync

if [[ -f $output_path/$PACKAGE_NAME ]]; then
    echo "Removing existing $PACKAGE_NAME ..."
    rm -f $output_path/$PACKAGE_NAME
fi

echo "Packaging extension $PACKAGE_NAME to $output_path"
excluded_files="agent.version packaging.sh apply_version.sh update_version.sh"
zip -r $output_path/$PACKAGE_NAME * -x $excluded_files "./test/*" "./extension-test/*" "./references" "./tmp"

# validate package size is within limits; these limits come from arc, ideally they are removed in the future
max_uncompressed_size=$((400 * 1024 * 1024))
max_compressed_size=$((275 * 1024 * 1024))

# easiest to validate by immediately unzipping versus trying to `du` with various exclusions 
unzip -d $output_path/unzipped $output_path/$PACKAGE_NAME
uncompressed_size=$(du -sb $output_path/unzipped | cut -f1)
compressed_size=$(du -sb $output_path/$PACKAGE_NAME | cut -f1)
rm -rf $output_path/unzipped

if [[ $uncompressed_size -gt $max_uncompressed_size ]]; then
    echo "Uncompressed size of $PACKAGE_NAME is $uncompressed_size bytes, which exceeds the limit of $max_uncompressed_size bytes"
    exit 1
fi

if [[ $compressed_size -gt $max_compressed_size ]]; then
    echo "Compressed size of $PACKAGE_NAME is $compressed_size bytes, which exceeds the limit of $max_compressed_size bytes"
    exit 1
fi

# cleanup newly added dir or files
rm -rf Utils/ waagent
