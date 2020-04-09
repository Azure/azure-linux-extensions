<#
.SYNOPSIS
    Wrapper around EV2VMExtnPackager script which creates extension EV2 artifacts.
#>
param(
    [Parameter(Mandatory=$True)]
    [string]$srcRoot,

    [Parameter(Mandatory=$True)]
    [string]$outputDir,

    [parameter(mandatory=$True)]
    [ValidateScript({Test-Path $_})]
    [string] $ExtensionInfoFile,

    [parameter(mandatory=$False)]
    [string] $BuildVersion
    )

$script_folder = Split-Path -Parent $MyInvocation.MyCommand.Definition

# moving to the source root folder for the python call
cd $srcRoot

# getting common parameters from the source
$common_parameters_path = "$srcRoot\main\common_parameters.json"
$common_parameters_original_content = Get-Content $common_parameters_path
$common_parameters = $common_parameters_original_content | ConvertFrom-Json 

# getting the specific ExtensionInfo file
[xml]$extension_info = Get-Content -Path $ExtensionInfoFile

# updating the extension name in common parameters from the ExtensionInfoFile
# this is needed for the python setup call
$common_parameters.extension_name = $extension_info.ExtensionInfo.Type
$common_parameters.extension_provider_namespace = $extension_info.ExtensionInfo.Namespace
$common_parameters | ConvertTo-Json | Set-Content $common_parameters_path -Force

# invoking Python packaging
python setup.py sdist --formats=zip

# removing a temporary manifest file from the source root folder
Remove-Item "$srcRoot\manifest.xml" -ErrorAction SilentlyContinue

# removing a temporary packaging folder
Remove-Item -Recurse "$srcRoot\dist\$($common_parameters.extension_name)-$($common_parameters.extension_version)" -ErrorAction SilentlyContinue

# restoring the original common parameters content
$common_parameters_original_content | Set-Content $common_parameters_path -Force

# preparing the output folder
Remove-Item  -Path $outputDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -Path $outputDir -ItemType Directory -Force

# setting ExtensionInfo values
$extension_info.ExtensionInfo.Version = $common_parameters.extension_version

# zip file format "<Namespace><Type>-<Version>.zip"
$extension_info.ExtensionInfo.ExtensionZipFileName = "$($extension_info.ExtensionInfo.Namespace).$($extension_info.ExtensionInfo.Type)-$($extension_info.ExtensionInfo.Version).zip"

# saving the updated extension info file
$temp_extension_info = "$outputDir/ExtensionInfo.xml"
$extension_info.Save($temp_extension_info)

# calling the packager
& "$script_folder\EV2VMExtnPackager.ps1" -outputDir $outputDir -ExtensionInfoFile $temp_extension_info -BuildVersion $BuildVersion

# moving the ZIP file to the EV2 folder
$original_zip_filepath = "$srcRoot\dist\$($common_parameters.extension_name)-$($common_parameters.extension_version).zip"
$ev2_zip_filepath = "$outputDir\ServiceGroupRoot\$($extension_info.ExtensionInfo.ExtensionZipFileName)"
Move-Item -Path $original_zip_filepath -Destination $ev2_zip_filepath