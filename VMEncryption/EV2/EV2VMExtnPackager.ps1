<#
.SYNOPSIS
    Generate the artifacts required for EV2 deployment for all environments for publishing VM Extensions
#>
param(
    [Parameter(Mandatory=$True, HelpMessage="Output directory where ServiceGroupRoot is created.")]
    [string]$outputDir,

    [parameter(mandatory=$True, HelpMessage="The extension info file with file path.")]
    [ValidateScript({Test-Path $_})]
    [string] $ExtensionInfoFile,

    [parameter(mandatory=$True, HelpMessage="The version of the build.")]
    [string] $BuildVersion = "1.0.0.0",

    [parameter(mandatory=$True, HelpMessage="True, if placeholder in zipFile name in ExtensionInfo file must be replaced with build version.")]
    [bool] $ReplaceBuildVersionInFileName = $false,

    [parameter(mandatory=$True, HelpMessage="True, if build version must be used as the VM extension version as well.")]
    [bool] $UseBuildVersionForExtnVersion = $false
    )

<#
.SYNOPSIS
    Get the payload properties for Uploading the extension
#>
function Get-UploadPayloadProperties
{
    [CmdletBinding()]
    param(
        [string] $ExtensionOperationName,
        [string] $ExtnZipFileName,
        [string] $ExtnStorageContainer,
        [string] $ExtnStorageAccountKVConnection
        )

    $AParametersValues_hash = [ordered]@{}
    $AParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $AParametersValues_hash -ParameterName "ExtensionOperationName" -ParameterValue "UploadExtension"
    $AParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $AParametersValues_hash -ParameterName "ContainerName" -ParameterValue "$($ExtnStorageContainer)"

    $APathHashtable = @{}
    $APathHashtable.Add("path","$($ExtnZipFileName)")
    $AReferenceHashtable = @{}
    $AReferenceHashtable.Add("reference",$APathHashtable)

    $AParametersValues_hash.Add("SASUri",$AReferenceHashtable)

    $KVStorageAccountSecretHashtable = @{}
    $KVStorageAccountSecretHashtable.Add("secretId", $ExtnStorageAccountKVConnection);

    $RefHashtable = @{}
    $RefHashtable.Add("provider", "AzureKeyVault")
    $RefHashtable.Add("parameters", $($KVStorageAccountSecretHashtable))

    $TargetStorageAccountSecretHashtable = @{}
    $TargetStorageAccountSecretHashtable.Add("reference", $RefHashtable)

    $AParametersValues_hash.Add("TargetStorageAccountSecret", $TargetStorageAccountSecretHashtable)

    $AParametersValues_hash
}

<#
.SYNOPSIS
    Get the rollout parameters for Uploading the extension
#>
function Get-RolloutParameterFileForUpload
{
    [CmdletBinding()]
    param(
        [string] $KVCertificateSecretPath, 
        [string] $ExtnZipFileName,
        [string] $ExtnStorageContainer,
        [string] $ExtnStorageAccountKVConnection,
        [string] $ExtnShortName,
        [string] $ServiceGroupRoot,
        [string] $CloudName
        )

    $ExtnPublishingStageName = "Upload-VMExtension"
    $ExtensionOperationName = "UploadExtension"
    $FileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath "Parameters" | Join-Path -ChildPath "Params_$($CloudName)_$($ExtnShortName)_CopyVMExtension.json"

    # Generate Rollout Parameters
    [string] $Parameter_Template_File = Get-RolloutParameterFileTemplate
    $Parameters_json = ConvertFrom-Json -InputObject $Parameter_Template_File

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Get-ConnectionParametersForRolloutParams -ExtnPublishingStageName $ExtnPublishingStageName `
                                                                        -KVCertificateSecretPath $KVCertificateSecretPath

    $UploadPayloadHash = Get-UploadPayloadProperties -ExtensionOperationName $ExtensionOperationName `
                                                        -ExtnZipFileName $ExtnZipFileName `
                                                        -ExtnStorageContainer $ExtnStorageContainer `
                                                        -ExtnStorageAccountKVConnection $ExtnStorageAccountKVConnection

    $ParametersValues_hash.Add("PayloadProperties", $UploadPayloadHash)
    
    $Parameters_json.Extensions += $ParametersValues_hash

    $Parameters_json | ConvertTo-Json -Depth 30 | out-file $FileWithPath -Encoding utf8 -Force
}

<#
.SYNOPSIS
    Create the folder, if it does not exist
#>
function Create-DeploymentFolder([string] $rootPath, [string] $subdirectory)
{
    [string]$path = Join-Path -Path $rootPath -ChildPath $subdirectory;

    if(!(Test-Path -Path $path))
    {
        $directory = New-Item -Path $path -ItemType directory -Force;
    }

    return $path;
}

<#
.SYNOPSIS
    Get the template file for Parameters
    Returns the json file like below

    {
        "$schema":  "http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#",
        "contentVersion":  "1.0.0.0",
        "paths":  [
                  ],
        "parameters":  {
                       }
    }

#>
function Get-ParameterFileTemplate
{
    [CmdletBinding()]
    param()

    $hashTemplateParameterFile = [ordered]@{}
    $emptyArray = @()
    $emptyHashtable = @{}

    $hashTemplateParameterFile.Add('$schema','http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#')
    $hashTemplateParameterFile.Add('contentVersion','1.0.0.0')
    $hashTemplateParameterFile.Add('paths',$emptyArray)
    $hashTemplateParameterFile.Add('parameters',$emptyHashtable)

    $hashTemplateParameterFile | ConvertTo-Json -Depth 10
}

<#
.SYNOPSIS
    Get the rollout parameters for Uploading the extension
#>
function Get-TemplateFile
{
    [CmdletBinding()]
    param(
        [string] $TemplateFilePath, 
        [string] $TemplateFileName
    )

    $TemplateFileWithPath = Join-Path -Path $TemplateFilePath -ChildPath $TemplateFileName

    $hashTemplateParameterFile = [ordered]@{}
    $emptyArray = @()
    $emptyHashtable = @{}

    $hashTemplateParameterFile.Add('$schema','http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#')
    $hashTemplateParameterFile.Add('contentVersion','1.0.0.0')
    $hashTemplateParameterFile.Add('parameters',$emptyHashtable)
    $hashTemplateParameterFile.Add('resources',$emptyArray)
    $hashTemplateParameterFile.Add('variables',$emptyHashtable)

    $hashTemplateParameterFile | ConvertTo-Json -Depth 10 | out-file $TemplateFileWithPath -Encoding utf8 -Force
}

<#
.SYNOPSIS
    Get the template for RolloutParameter file
    Returns the json file like below

    {
        "$schema":  "http://schema.express.azure.com/schemas/2015-01-01-alpha/RolloutParameters.json",
        "ContentVersion":  "1.0.0.0",
        "Extensions":  [
                  ],
        "parameters":  {
                       }
    }

#>
function Get-RolloutParameterFileTemplate
{
    [CmdletBinding()]
    param()

    $hashTemplateParameterFile = [ordered]@{}
    $emptyArray = @()
    
    $hashTemplateParameterFile.Add('$schema','http://schema.express.azure.com/schemas/2015-01-01-alpha/RolloutParameters.json')
    $hashTemplateParameterFile.Add('ContentVersion','1.0.0.0')
    $hashTemplateParameterFile.Add('Extensions',$emptyArray)
    
    $hashTemplateParameterFile | ConvertTo-Json -Depth 10
}

<#
.SYNOPSIS
    Adds the parameter and value to the parameters hashtable
#>
function Add-ParameterToHashtable
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$True)]
        $ParametersHashtable,
        
        [Parameter(Mandatory=$True)]
        $ParameterName,

        [Parameter(Mandatory=$True)]
        $ParameterValue
    )

    $parameterValueInFile = @{"value" = "$ParameterValue"}
    $ParametersHashtable.Add("$ParameterName", $parameterValueInFile)

    $ParametersHashtable
}

<#
.SYNOPSIS
    Get part of the Rollout parameters
#>
function Get-ConnectionParametersForRolloutParams
{
    [CmdletBinding()]
    param(
        [string] $ExtnPublishingStageName,
        [string] $KVCertificateSecretPath
        )

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash.Add("Name", "$($ExtnPublishingStageName)")
    $ParametersValues_hash.Add("Type", "Microsoft.SiteRecovery/PublishPlatformExtensions")
    $ParametersValues_hash.Add("Version", "2018-10-01")

    $PublishingCertificateHashtable = @{}
    $PublishingCertificateHashtable.Add("SecretId","$($KVCertificateSecretPath)")

    $ReferenceHashtable = @{}
    $ReferenceHashtable.Add("Provider", "AzureKeyVault")
    $ReferenceHashtable.Add("Parameters", $PublishingCertificateHashtable)

    $AuthenticationHashtable = @{}
    $AuthenticationHashtable.Add("Type","CertificateAuthentication")
    $AuthenticationHashtable.Add("Reference", $ReferenceHashtable)

    $ConnectionPropertiesHashtable = @{}
    $ConnectionPropertiesHashtable.Add("MaxExecutionTime", "PT24H")
    $ConnectionPropertiesHashtable.Add("Authentication", $AuthenticationHashtable)

    $ParametersValues_hash.Add("ConnectionProperties", $ConnectionPropertiesHashtable)

    $ParametersValues_hash
}

<#
.SYNOPSIS
    Get the rollout parameter file
#>
function Get-RolloutParameterFile
{
    [CmdletBinding()]
    param(
        [string] $ServiceGroupRoot,
        [string] $CloudName,
        [xml] $ExtnInfoXml,
        [bool] $ReplaceBuildVersionInFileName,
        [string] $BuildVersion,
        [bool] $UseBuildVersionForExtnVersion
        )

    $KVCertificateSecretPath = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).KVPathForCertSecret
    $PublishingSubscriptionId = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SubscriptionId
    $ExtnStorageAccountKVConnection = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).KVClassicStorageConnection
    $ExtnStorageContainer = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).ClassicContainerName
    $ExtnNamespace = $ExtnInfoXml.ExtensionInfo.Namespace
    $ExtnType = $ExtnInfoXml.ExtensionInfo.Type
    $ExtnIsInternal = $ExtnInfoXml.ExtensionInfo.ExtensionIsAlwaysInternal
    $ExtnSupportedOS = $ExtnInfoXml.ExtensionInfo.SupportedOS
    $ExtnLabel = $ExtnInfoXml.ExtensionInfo.ExtensionLabel
    $ExtnShortName = $ExtnInfoXml.ExtensionInfo.ExtensionShortName

    $ExtnVersion = $ExtnInfoXml.ExtensionInfo.Version
    if($UseBuildVersionForExtnVersion)
    {
        $ExtnVersion = $BuildVersion
    }

    $ExtnZipFileName = $ExtnInfoXml.ExtensionInfo.ExtensionZipFileName
    if($ReplaceBuildVersionInFileName)
    {
        $ExtnZipFileName = $ExtnZipFileName -replace '==buildversion==', $BuildVersion
    }

    $ExtnStorageAccountEndpointSuffix = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).StorageAccountEndpointSuffix
    $ExtnStorageAccountName = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).ClassicStorageAccountName
    $ExtnBlobUri = "https://$($ExtnStorageAccountName).$($ExtnStorageAccountEndpointSuffix)/$($ExtnStorageContainer)/$($ExtnZipFileName)"

    $SDPStageCount = ($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions | select -ExpandProperty childnodes | where {$_.name -like 'Stage*'}).Count


    Get-RolloutParameterFileForUpload -KVCertificateSecretPath $KVCertificateSecretPath `
                                        -ExtnZipFileName $ExtnZipFileName `
                                        -ExtnStorageContainer $ExtnStorageContainer `
                                        -ExtnStorageAccountKVConnection $ExtnStorageAccountKVConnection `
                                        -ExtnShortName $ExtnShortName `
                                        -ServiceGroupRoot $ServiceGroupRoot `
                                        -CloudName $CloudName

    Get-RolloutParameterFileForGetExtns -KVCertificateSecretPath $KVCertificateSecretPath `
                                        -SubscriptionId $PublishingSubscriptionId `
                                        -ExtnShortName $ExtnShortName `
                                        -ServiceGroupRoot $ServiceGroupRoot `
                                        -CloudName $CloudName

    Get-RolloutParameterFileForRegister -KVCertificateSecretPath $KVCertificateSecretPath `
                                        -SubscriptionId $PublishingSubscriptionId `
                                        -ExtnNamespace $ExtnNamespace `
                                        -ExtnType $ExtnType `
                                        -ExtnVersion $ExtnVersion `
                                        -ExtnBlobUri $ExtnBlobUri `
                                        -ExtnSupportedOS $ExtnSupportedOS `
                                        -ExtnLabel $ExtnLabel `
                                        -ExtnShortName $ExtnShortName `
                                        -ServiceGroupRoot $ServiceGroupRoot `
                                        -CloudName $CloudName

    for($i=1; $i -le $SDPStageCount; $i++)
    {
        $stageName = "Stage$($i)"
        $ExtnRegions = $($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions.$stageName)

        Get-RolloutParameterFileForPromote -KVCertificateSecretPath $KVCertificateSecretPath `
                                            -SubscriptionId $PublishingSubscriptionId `
                                            -ExtnNamespace $ExtnNamespace `
                                            -ExtnType $ExtnType `
                                            -ExtnVersion $ExtnVersion `
                                            -ExtnIsInternal $ExtnIsInternal `
                                            -ExtnRegions $ExtnRegions `
                                            -SDPStage $stageName `
                                            -ExtnShortName $ExtnShortName `
                                            -ServiceGroupRoot $ServiceGroupRoot `
                                            -CloudName $CloudName
    }

    # Get parameters for promoting the extension in ALL regions (value = Public)
        Get-RolloutParameterFileForPromote -KVCertificateSecretPath $KVCertificateSecretPath `
                                            -SubscriptionId $PublishingSubscriptionId `
                                            -ExtnNamespace $ExtnNamespace `
                                            -ExtnType $ExtnType `
                                            -ExtnVersion $ExtnVersion `
                                            -ExtnIsInternal $ExtnIsInternal `
                                            -ExtnRegions "Public" `
                                            -SDPStage "All" `
                                            -ExtnShortName $ExtnShortName `
                                            -ServiceGroupRoot $ServiceGroupRoot `
                                            -CloudName $CloudName
}

<#
.SYNOPSIS
    Get the rollout parameters for Promoting the extension
#>
function Get-RolloutParameterFileForPromote
{
    [CmdletBinding()]
    param(
        [string] $KVCertificateSecretPath, 
        [string] $SubscriptionId,
        [string] $ExtnNamespace,
        [string] $ExtnType,
        [string] $ExtnVersion,
        [string] $ExtnIsInternal,
        [string] $ExtnRegions,
        [string] $SDPStage,
        [string] $ExtnShortName,
        [string] $ServiceGroupRoot,
        [string] $CloudName
        )

    $ExtnPublishingStageName = "Promote-$($SDPStage)"
    $ExtensionOperationName = "UpdateExtension"
    $FileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath "Parameters" | Join-Path -ChildPath "Params_$($CloudName)_$($ExtnShortName)_Promote_$($SDPStage).json"

    # Generate Rollout Parameters
    [string] $Parameter_Template_File = Get-RolloutParameterFileTemplate
    $Parameters_json = ConvertFrom-Json -InputObject $Parameter_Template_File

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Get-ConnectionParametersForRolloutParams -ExtnPublishingStageName $ExtnPublishingStageName `
                                                                        -KVCertificateSecretPath $KVCertificateSecretPath

    $PayloadHashtable = Get-PromoteExtnProperties -ExtensionOperationName $ExtensionOperationName `
                                                        -SubscriptionId $SubscriptionId `
                                                        -KVCertificateSecretPath $KVCertificateSecretPath `
                                                        -ExtnNamespace $ExtnNamespace `
                                                        -ExtnType $ExtnType `
                                                        -ExtnVersion $ExtnVersion `
                                                        -ExtnIsInternal $ExtnIsInternal `
                                                        -ExtnRegions $ExtnRegions

    $ParametersValues_hash.Add("PayloadProperties", $PayloadHashtable)
    
    $Parameters_json.Extensions += $ParametersValues_hash

    $Parameters_json | ConvertTo-Json -Depth 30 | out-file $FileWithPath -Encoding utf8 -Force
}

<#
.SYNOPSIS
    Get some of the the properties value for promoting the extension
#>
function Get-PromoteExtnProperties
{
    [CmdletBinding()]
    param(
        [string] $ExtensionOperationName, 
        [string] $SubscriptionId,
        [string] $KVCertificateSecretPath,
        [string] $ExtnNamespace,
        [string] $ExtnType,
        [string] $ExtnVersion,
        [string] $ExtnIsInternal,
        [string] $ExtnRegions
        )

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionOperationName" -ParameterValue "$($ExtensionOperationName)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "SubscriptionId" -ParameterValue "$($SubscriptionId)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionProviderNameSpace" -ParameterValue "$($ExtnNamespace)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionName" -ParameterValue "$($ExtnType)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionVersion" -ParameterValue "$($ExtnVersion)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "IsInternal" -ParameterValue "$($ExtnIsInternal)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "Regions" -ParameterValue "$($ExtnRegions)"

    $KVCertificateSecretPathHashtable = @{}
    $KVCertificateSecretPathHashtable.Add("secretId", $KVCertificateSecretPath);

    $RefHashtable = @{}
    $RefHashtable.Add("provider", "AzureKeyVault")
    $RefHashtable.Add("parameters", $($KVCertificateSecretPathHashtable))

    $ManagementCertificateHashtable = @{}
    $ManagementCertificateHashtable.Add("reference", $RefHashtable)

    $ParametersValues_hash.Add("ManagementCertificate", $ManagementCertificateHashtable)

    $ParametersValues_hash
}

<#
.SYNOPSIS
    Get the rollout parameters for Registering the extension
#>
function Get-RolloutParameterFileForRegister
{
    [CmdletBinding()]
    param(
        [string] $KVCertificateSecretPath, 
        [string] $SubscriptionId,
        [string] $ExtnNamespace,
        [string] $ExtnType,
        [string] $ExtnVersion,
        [string] $ExtnBlobUri,
        [string] $ExtnSupportedOS,
        [string] $ExtnLabel,
        [string] $ExtnShortName,
        [string] $ServiceGroupRoot,
        [string] $CloudName
        )

    $ExtnPublishingStageName = "Register-VMExtension"
    $ExtensionOperationName = "RegisterExtension"
    $FileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath "Parameters" | Join-Path -ChildPath "Params_$($CloudName)_$($ExtnShortName)_Register.json"

    # Generate Rollout Parameters
    [string] $Parameter_Template_File = Get-RolloutParameterFileTemplate
    $Parameters_json = ConvertFrom-Json -InputObject $Parameter_Template_File

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Get-ConnectionParametersForRolloutParams -ExtnPublishingStageName $ExtnPublishingStageName `
                                                                        -KVCertificateSecretPath $KVCertificateSecretPath

    $PayloadHashtable = Get-RegisterExtnProperties -ExtensionOperationName $ExtensionOperationName `
                                                        -SubscriptionId $SubscriptionId `
                                                        -KVCertificateSecretPath $KVCertificateSecretPath `
                                                        -ExtnNamespace $ExtnNamespace `
                                                        -ExtnType $ExtnType `
                                                        -ExtnVersion $ExtnVersion `
                                                        -ExtnBlobUri $ExtnBlobUri `
                                                        -ExtnSupportedOS $ExtnSupportedOS `
                                                        -ExtnLabel $ExtnLabel

    $ParametersValues_hash.Add("PayloadProperties", $PayloadHashtable)
    
    $Parameters_json.Extensions += $ParametersValues_hash

    $Parameters_json | ConvertTo-Json -Depth 30 | out-file $FileWithPath -Encoding utf8 -Force
}

<#
.SYNOPSIS
    Get some of the the properties for Registering the extension
#>
function Get-RegisterExtnProperties
{
    [CmdletBinding()]
    param(
        [string] $ExtensionOperationName, 
        [string] $SubscriptionId,
        [string] $KVCertificateSecretPath,
        [string] $ExtnNamespace,
        [string] $ExtnType,
        [string] $ExtnVersion,
        [string] $ExtnBlobUri,
        [string] $ExtnSupportedOS,
        [string] $ExtnLabel
        )

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionOperationName" -ParameterValue "$($ExtensionOperationName)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "SubscriptionId" -ParameterValue "$($SubscriptionId)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionProviderNameSpace" -ParameterValue "$($ExtnNamespace)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionName" -ParameterValue "$($ExtnType)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionVersion" -ParameterValue "$($ExtnVersion)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "BlobUri" -ParameterValue "$($ExtnBlobUri)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "SupportedOS" -ParameterValue "$($ExtnSupportedOS)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "Label" -ParameterValue "$($ExtnLabel)"

    $KVCertificateSecretPathHashtable = @{}
    $KVCertificateSecretPathHashtable.Add("secretId", $KVCertificateSecretPath);

    $RefHashtable = @{}
    $RefHashtable.Add("provider", "AzureKeyVault")
    $RefHashtable.Add("parameters", $($KVCertificateSecretPathHashtable))

    $ManagementCertificateHashtable = @{}
    $ManagementCertificateHashtable.Add("reference", $RefHashtable)

    $ParametersValues_hash.Add("ManagementCertificate", $ManagementCertificateHashtable)

    $ParametersValues_hash
}

<#
.SYNOPSIS
    Get the rollout parameters for Listing the extensions
#>
function Get-RolloutParameterFileForGetExtns
{
    [CmdletBinding()]
    param(
        [string] $KVCertificateSecretPath, 
        [string] $SubscriptionId,
        [string] $ExtnShortName,
        [string] $ServiceGroupRoot,
        [string] $CloudName
        )

    $ExtnPublishingStageName = "GetPublishedExtensions"
    $ExtensionOperationName = "GetAllPublishedExtensions"
    $FileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath "Parameters" | Join-Path -ChildPath "Params_$($CloudName)_$($ExtnShortName)_GetExtensions.json"

    # Generate Rollout Parameters
    [string] $Parameter_Template_File = Get-RolloutParameterFileTemplate
    $Parameters_json = ConvertFrom-Json -InputObject $Parameter_Template_File

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Get-ConnectionParametersForRolloutParams -ExtnPublishingStageName $ExtnPublishingStageName `
                                                                        -KVCertificateSecretPath $KVCertificateSecretPath

    $PayloadHashtable = Get-GetExtnProperties -ExtensionOperationName $ExtensionOperationName `
                                                        -SubscriptionId $SubscriptionId `
                                                        -KVCertificateSecretPath $KVCertificateSecretPath

    $ParametersValues_hash.Add("PayloadProperties", $PayloadHashtable)
    
    $Parameters_json.Extensions += $ParametersValues_hash

    $Parameters_json | ConvertTo-Json -Depth 30 | out-file $FileWithPath -Encoding utf8 -Force
}

<#
.SYNOPSIS
    Get some of the properties for Listing the extension
#>
function Get-GetExtnProperties
{
    [CmdletBinding()]
    param(
        [string] $ExtensionOperationName, 
        [string] $SubscriptionId,
        [string] $KVCertificateSecretPath
        )

    $ParametersValues_hash = [ordered]@{}
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "ExtensionOperationName" -ParameterValue "$($ExtensionOperationName)"
    $ParametersValues_hash = Add-ParameterToHashtable -ParametersHashtable $ParametersValues_hash -ParameterName "SubscriptionId" -ParameterValue "$($SubscriptionId)"

    $KVCertificateSecretPathHashtable = @{}
    $KVCertificateSecretPathHashtable.Add("secretId", $KVCertificateSecretPath);

    $RefHashtable = @{}
    $RefHashtable.Add("provider", "AzureKeyVault")
    $RefHashtable.Add("parameters", $($KVCertificateSecretPathHashtable))

    $ManagementCertificateHashtable = @{}
    $ManagementCertificateHashtable.Add("reference", $RefHashtable)

    $ParametersValues_hash.Add("ManagementCertificate", $ManagementCertificateHashtable)

    $ParametersValues_hash
}

<#
.SYNOPSIS
    Get the ServiceModel File
#>
function Get-ServiceModelFile
{
    [CmdletBinding()]
    param(
        [string] $ServiceGroupRoot,
        [string] $CloudName,
        [xml] $ExtnInfoXml
        )

    switch($CloudName)
    {
        "Public" 
            {
                $Ev2Environment = "Public"
                $AzureFunctionLocation = "Southeast Asia"
                $AzureFunctionResourceGroup = "TBD"
                break
            }
        "Blackforest"
            {
                $Ev2Environment = "Blackforest"
                $AzureFunctionLocation = "Germany Central"
                $AzureFunctionResourceGroup = "TBD"
            }
        "Mooncake"
            {
                $Ev2Environment = "Mooncake"
                $AzureFunctionLocation = "China East"
                $AzureFunctionResourceGroup = "TBD"
            }
        "Fairfax"
            {
                $Ev2Environment = "Fairfax"
                $AzureFunctionLocation = "USDoD Central"
                $AzureFunctionResourceGroup = "TBD"
            }
        default
            {
                $Ev2Environment = "TBD"
                $AzureFunctionSubscriptionId = "TBD"
                $AzureFunctionLocation = "TBD"
                $AzureFunctionResourceGroup = "TBD"
                break
            }
    }

    $ExtnShortName = $ExtnInfoXml.ExtensionInfo.ExtensionShortName
    $AzureFunctionSubscriptionId = $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SubscriptionId
    $ServiceModelTemplate = Get-ServiceModelTemplateFile -Ev2Environment $Ev2Environment

    $ServiceResourceGroups = @()

    $ServiceResourceGroupHash = @{}
    $ServiceResourceGroupHash.Add("AzureResourceGroupName","$AzureFunctionResourceGroup")
    $ServiceResourceGroupHash.Add("Location","$AzureFunctionLocation")
    $ServiceResourceGroupHash.Add("InstanceOf","ExtensionPublishResource_Instance")
    $ServiceResourceGroupHash.Add("AzureSubscriptionId","$AzureFunctionSubscriptionId")

    $ServiceResources = @()

    # =======================
    # Copy extension to storage account

    $ServiceResourceHashtable = @{}
    $ServiceResourceHashtable.Add("Name","Copy-VMExtension2Container")
    $ServiceResourceHashtable.Add("InstanceOf","ExtensionPublishResource_ServiceResource")
    $ServiceResourceHashtable.Add("ArmParametersPath","Parameters\ArmParameters.json")
    $ServiceResourceHashtable.Add("RolloutParametersPath","Parameters\Params_$($CloudName)_$($ExtnShortName)_CopyVMExtension.json")

    $ServiceResources += $ServiceResourceHashtable

    # =======================
    # Register

    $ServiceResourceHashtable = @{}
    $ServiceResourceHashtable.Add("Name","ExtensionPublishResource")
    $ServiceResourceHashtable.Add("InstanceOf","ExtensionPublishResource_ServiceResource")
    $ServiceResourceHashtable.Add("ArmParametersPath","Parameters\ArmParameters.json")
    $ServiceResourceHashtable.Add("RolloutParametersPath","Parameters\Params_$($CloudName)_$($ExtnShortName)_Register.json")

    $ServiceResources += $ServiceResourceHashtable

    # =======================
    # Get Published Extensions

    $ServiceResourceHashtable = @{}
    $ServiceResourceHashtable.Add("Name","GetPublishedExtensions")
    $ServiceResourceHashtable.Add("InstanceOf","ExtensionPublishResource_ServiceResource")
    $ServiceResourceHashtable.Add("ArmParametersPath","Parameters\ArmParameters.json")
    $ServiceResourceHashtable.Add("RolloutParametersPath","Parameters\Params_$($CloudName)_$($ExtnShortName)_GetExtensions.json")

    $ServiceResources += $ServiceResourceHashtable

    # =======================
    # Promote to regions

    $SDPStageCount = ($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions | select -ExpandProperty childnodes | where {$_.name -like 'Stage*'}).Count

    for($i=1; $i -le $SDPStageCount; $i++)
    {
        $stageName = "PromoteStage$($i)"
        $FileName = "Promote_Stage$($i)"
        $rolloutParameterFile = "Parameters\Params_$($CloudName)_$($ExtnShortName)_$($FileName).json"

        $ServiceResourceHashtable = @{}
        $ServiceResourceHashtable.Add("Name","$stageName")
        $ServiceResourceHashtable.Add("InstanceOf","ExtensionPublishResource_ServiceResource")
        $ServiceResourceHashtable.Add("ArmParametersPath","Parameters\ArmParameters.json")
        $ServiceResourceHashtable.Add("RolloutParametersPath","$rolloutParameterFile")

        $ServiceResources += $ServiceResourceHashtable
    }

    # =======================
    # Promote to ALL regions

    $ServiceResourceHashtable = @{}
    $ServiceResourceHashtable.Add("Name","PromoteAll")
    $ServiceResourceHashtable.Add("InstanceOf","ExtensionPublishResource_ServiceResource")
    $ServiceResourceHashtable.Add("ArmParametersPath","Parameters\ArmParameters.json")
    $ServiceResourceHashtable.Add("RolloutParametersPath","Parameters\Params_$($CloudName)_$($ExtnShortName)_Promote_All.json")

    $ServiceResources += $ServiceResourceHashtable
    # =======================

    $ServiceResourceGroupHash.Add("ServiceResources",$ServiceResources)

    $ServiceResourceGroups += $ServiceResourceGroupHash

    $ServiceModelTemplate.Add("ServiceResourceGroups", $ServiceResourceGroups)

    $ServiceModelFile = Join-Path -Path $ServiceGroupRoot -ChildPath "$($CloudName)_$($ExtnShortName)_ServiceModel.json"

    $ServiceModelTemplate | ConvertTo-Json -Depth 30 | Out-File $ServiceModelFile -Encoding utf8 -Force
}

<#
.SYNOPSIS
    Helper to get the servicemodel file
#>
function Get-ServiceModelTemplateFile
{
    [CmdletBinding()]
    param(
        [string] $Ev2Environment
        )

    $hashTemplateServiceModelFile = [ordered]@{}
    $emptyArray = @()
    $emptyHashtable = @{}

    $ServiceMetadataHashtable = @{}
    $ServiceMetadataHashtable.Add("ServiceGroup","VMExtension")
    $ServiceMetadataHashtable.Add("Environment","$($Ev2Environment)")

    $hashTemplateServiceModelFile.Add('$schema','http://schema.express.azure.com/schemas/2015-01-01-alpha/ServiceModel.json')
    $hashTemplateServiceModelFile.Add('ContentVersion','1.0.0.0')
    $hashTemplateServiceModelFile.Add('ServiceMetadata',$ServiceMetadataHashtable)

    $ServiceResourceDefinitionsArray = @()

    $ServiceResourceDefinitionsHashtable = @{}
    $ServiceResourceDefinitionsHashtable.Add("Name","ExtensionPublishResource_ServiceResource")
    $ServiceResourceDefinitionsHashtable.Add("ArmTemplatePath","Templates\UpdateConfig.Template.json")

    $ServiceResourceDefinitionsArray += $ServiceResourceDefinitionsHashtable

    $ServiceResourceGroupDefinitionsHashtable = @{}
    $ServiceResourceGroupDefinitionsHashtable.Add("Name","ExtensionPublishResource_Instance")
    $ServiceResourceGroupDefinitionsHashtable.Add("ServiceResourceDefinitions", $ServiceResourceDefinitionsArray)

    $ServiceResourceGroupDefinitionsArray = @()
    $ServiceResourceGroupDefinitionsArray += $ServiceResourceGroupDefinitionsHashtable
    $hashTemplateServiceModelFile.Add('ServiceResourceGroupDefinitions',$ServiceResourceGroupDefinitionsArray)

    $hashTemplateServiceModelFile 
}

<#
.SYNOPSIS
    Get all the the rollout specs for the given Cloud
#>
function Get-AllRolloutSpecFiles
{
    [CmdletBinding()]
    param(
        [string] $ServiceGroupRoot,
        [string] $CloudName,
        [xml] $ExtnInfoXml,
        [bool] $UseBuildVersionForExtnVersion,
        [string] $BuildVersion
        )

    $ExtnVersion = $ExtnInfoXml.ExtensionInfo.Version
    if($UseBuildVersionForExtnVersion)
    {
        $ExtnVersion = $BuildVersion
    }

    $ExtnShortName = $ExtnInfoXml.ExtensionInfo.ExtensionShortName
    $ServiceModelPath = "$($CloudName)_$($ExtnShortName)_ServiceModel.json"

    # ===============================
    # List all extensions
    $StepName = "Get-PublishedExtensions"
    $TargetName = "GetPublishedExtensions"
    $ActionName = "GetPublishedExtensions"
    $RolloutSpecFileName = "RolloutSpec_$($CloudName)_$($ExtnShortName)_ListAll.json"
    $RolloutSpecFileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath $RolloutSpecFileName
    
    Get-RolloutSpecFile -StepName $StepName `
                        -TargetName $TargetName `
                        -ActionName $ActionName `
                        -ServiceModelPath $ServiceModelPath `
                        -ExtnShortName $ExtnShortName `
                        -ExtnVersion $ExtnVersion `
                        -RolloutSpecFileWithPath $RolloutSpecFileWithPath

    # ===============================
    # Upload extension
    $StepName = "Upload-VMExtension"
    $TargetName = "Copy-VMExtension2Container"
    $ActionName = "Upload-VMExtension"
    $RolloutSpecFileName = "RolloutSpec_$($CloudName)_$($ExtnShortName)_Upload.json"
    $RolloutSpecFileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath $RolloutSpecFileName
    
    Get-RolloutSpecFile -StepName $StepName `
                        -TargetName $TargetName `
                        -ActionName $ActionName `
                        -ServiceModelPath $ServiceModelPath `
                        -ExtnShortName $ExtnShortName `
                        -ExtnVersion $ExtnVersion `
                        -RolloutSpecFileWithPath $RolloutSpecFileWithPath

    # ===============================
    # Register extension
    $StepName = "Register-VMExtension"
    $TargetName = "ExtensionPublishResource"
    $ActionName = "Register-VMExtension"
    $RolloutSpecFileName = "RolloutSpec_$($CloudName)_$($ExtnShortName)_Register.json"
    $RolloutSpecFileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath $RolloutSpecFileName
    
    Get-RolloutSpecFile -StepName $StepName `
                        -TargetName $TargetName `
                        -ActionName $ActionName `
                        -ServiceModelPath $ServiceModelPath `
                        -ExtnShortName $ExtnShortName `
                        -ExtnVersion $ExtnVersion `
                        -RolloutSpecFileWithPath $RolloutSpecFileWithPath

    # ===============================
    # Promote SDP stages

    $SDPStageCount = ($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions | select -ExpandProperty childnodes | where {$_.name -like 'Stage*'}).Count

    for($i=1; $i -le $SDPStageCount; $i++)
    {
        $stageName = "Stage$($i)"

        $StepName = "Promote-$stageName"
        $TargetName = "Promote$stageName"
        $ActionName = "Promote-$stageName"
        $RolloutSpecFileName = "RolloutSpec_$($CloudName)_$($ExtnShortName)_Promote$stageName.json"
        $RolloutSpecFileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath $RolloutSpecFileName

        Get-RolloutSpecFile -StepName $StepName `
                            -TargetName $TargetName `
                            -ActionName $ActionName `
                            -ServiceModelPath $ServiceModelPath `
                            -ExtnShortName $ExtnShortName `
                            -ExtnVersion $ExtnVersion `
                            -RolloutSpecFileWithPath $RolloutSpecFileWithPath
        }

    # ===============================
    # Promote All
    $StepName = "Promote-All"
    $TargetName = "PromoteAll"
    $ActionName = "Promote-All"
    $RolloutSpecFileName = "RolloutSpec_$($CloudName)_$($ExtnShortName)_PromoteAll.json"
    $RolloutSpecFileWithPath = Join-Path -Path $ServiceGroupRoot -ChildPath $RolloutSpecFileName
    
    Get-RolloutSpecFile -StepName $StepName `
                        -TargetName $TargetName `
                        -ActionName $ActionName `
                        -ServiceModelPath $ServiceModelPath `
                        -ExtnShortName $ExtnShortName `
                        -ExtnVersion $ExtnVersion `
                        -RolloutSpecFileWithPath $RolloutSpecFileWithPath

}

<#
.SYNOPSIS
    Helper to get the rollout spec file
#>
function Get-RolloutSpecFile
{
    [CmdletBinding()]
    param(
        [string] $StepName,
        [string] $TargetName,
        [string] $ActionName,
        [string] $ServiceModelPath,
        [string] $ExtnShortName,
        [string] $ExtnVersion,
        [string] $RolloutSpecFileWithPath
        )

    $hashTemplateRolloutSpec = [ordered]@{}

    $emptyArray = @()
    $emptyHashtable = @{}
    $ServiceMetadataHashtable = @{}

    $hashTemplateRolloutSpec.Add('$schema',"http://schema.express.azure.com/schemas/2015-01-01-alpha/RolloutSpec.json")
    $hashTemplateRolloutSpec.Add("ContentVersion","1.0.0.0")

    $rolloutMetadataHashtable = @{}
    $rolloutMetadataHashtable.Add("ServiceModelPath", $ServiceModelPath)
    $rolloutMetadataHashtable.Add("Name", "$ExtnShortName $ExtnVersion")
    $rolloutMetadataHashtable.Add("RolloutType", "Hotfix")

    $ParametersHash = @{}
    $ParametersHash.Add("ServiceGroupRoot","ServiceGroupRoot")
    $ParametersHash.Add("VersionFile","buildver.txt")

    $BuildSourceHashtable = @{}
    $BuildSourceHashtable.Add("BuildSourceType","SmbShare")
    $BuildSourceHashtable.Add("Parameters", $ParametersHash)

    $rolloutMetadataHashtable.Add("BuildSource", $BuildSourceHashtable)

    $hashTemplateRolloutSpec.Add("RolloutMetadata", $rolloutMetadataHashtable)

    $OrchestratedSteps = @()
    $OrchestratedStepHashTable = @{}

    $OrchestratedStepHashTable.Add("Name","$StepName")
    $OrchestratedStepHashTable.Add("TargetType","ServiceResource")
    $OrchestratedStepHashTable.Add("TargetName","$TargetName")
    $ActionsArray = @("Extension/$($ActionName)")
    $OrchestratedStepHashTable.Add("Actions",$ActionsArray)

    $OrchestratedSteps += $OrchestratedStepHashTable

    $hashTemplateRolloutSpec.Add("OrchestratedSteps", $OrchestratedSteps)

    $hashTemplateRolloutSpec | ConvertTo-Json -Depth 30 | Out-File $RolloutSpecFileWithPath -Encoding utf8 -Force
}


<#
.SYNOPSIS
    Check if the input object is null or empty. If yes, Throw exception and exit
#>
function IfNullThrowAndExit
{
    [CmdletBinding()]
    param(
        $inputObject,

        [string] $ErrorMessage
        )

    if([string]::IsNullOrWhiteSpace($inputObject))
    {
        throw $ErrorMessage
        exit
    }
}

<#
.SYNOPSIS
    Throw the give exception and exit
#>
function ThrowAndExit
{
    [CmdletBinding()]
    param(
        [string] $ErrorMessage
        )

    throw $ErrorMessage
    exit
}

<#
.SYNOPSIS
    Validate the ExtensionInfo xml file
#>
function Validate-ExtensionInfoFile
{
    [CmdletBinding()]
    param(
        [xml] $ExtnInfoXml
        )

    IfNullThrowAndExit -inputObject $ExtnInfoXml -ErrorMessage "xml file is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo -ErrorMessage "ExtensionInfo node not found in XML."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.Namespace -ErrorMessage "Extension Namespace is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.Type.Trim() -ErrorMessage "Extension Type is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.Version.Trim() -ErrorMessage "Extension Version is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.ExtensionShortName.Trim() -ErrorMessage "Extension ShortName is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.SupportedOS.Trim() -ErrorMessage "Extension SupportedOS is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.ExtensionLabel.Trim() -ErrorMessage "Extension Label is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.ExtensionZipFileName.Trim() -ErrorMessage "Extension ZipFile is null."
    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.ExtensionIsAlwaysInternal.Trim() -ErrorMessage "ExtensionIsAlwaysInternal is null."

    # ExtensionIsAlwaysInternal must be True or False only
    if(!($ExtnInfoXml.ExtensionInfo.ExtensionIsAlwaysInternal -ieq "True" -or $ExtnInfoXml.ExtensionInfo.ExtensionIsAlwaysInternal -ieq "False"))
    {
        ThrowAndExit -ErrorMessage "ExtensionIsAlwaysInternal must be True or False only."
    }

    # SupportedOS must be Windows or Linux only
    if(!($ExtnInfoXml.ExtensionInfo.SupportedOS -ieq "Windows" -or $ExtnInfoXml.ExtensionInfo.SupportedOS -ieq "Linux"))
    {
        ThrowAndExit -ErrorMessage "SupportedOS must be Windows or Linux only."
    }
    
    if ($ExtnInfoXml.ExtensionInfo.ExtensionShortName -contains " ")
    {
        ThrowAndExit -ErrorMessage "ShortName must not contain spaces."
    }

    IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes -ErrorMessage "CloudTypes node not found."

    if($ExtnInfoXml.ExtensionInfo.CloudTypes.ChildNodes.Count -le 0)
    {
        ThrowAndExit -ErrorMessage "CloudTypes not specified. Check the ExtensionInfo file."
    }

    foreach ($CloudType in $ExtensionInfoXmlContent.ExtensionInfo.CloudTypes.ChildNodes)
    {
        $CloudName =  $CloudType.Name

        if(!($CloudName -ieq "Public" -or $CloudName -ieq "Blackforest" -or $CloudName -ieq "Mooncake" -or $CloudName -ieq "Fairfax"))
        {
            ThrowAndExit -ErrorMessage "CloudTypes supported at this time are Public, Blackforest, Mooncake, Fairfax. Not '$($CloudName)'."
        }

        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SubscriptionId -ErrorMessage "SubscriptionId for Cloud $($CloudName) is not valid."
        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).KVPathForCertSecret -ErrorMessage "KVPathForCertSecret for Cloud $($CloudName) is not valid."
        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).ClassicStorageAccountName -ErrorMessage "ClassicStorageAccountName for Cloud $($CloudName) is not valid."
        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).ClassicContainerName -ErrorMessage "ClassicContainerName for Cloud $($CloudName) is not valid."
        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).StorageAccountEndpointSuffix -ErrorMessage "StorageAccountEndpointSuffix for Cloud $($CloudName) is not valid."
        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).KVClassicStorageConnection -ErrorMessage "KVClassicStorageConnection for Cloud $($CloudName) is not valid."

        IfNullThrowAndExit -inputObject $ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions -ErrorMessage "SDPRegions for Cloud $($CloudName) is not valid."

        $SDPStageCount = ($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions | select -ExpandProperty childnodes | where {$_.name -like 'Stage*'}).Count
        
        if($SDPStageCount -lt 2)
        {
            ThrowAndExit -ErrorMessage "SDP is not being followed for $($CloudName)."
        }

        for($i=1; $i -lt $SDPStageCount; $i++)
        {
            $stageName = "Stage$($i)"
            $ExtnRegions = $($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions.$stageName)

            IfNullThrowAndExit -inputObject $ExtnRegions -ErrorMessage "Stage $($stageName) in $($CloudName) is not valid."

            $nextStage = "Stage$($i + 1)"
            $NextStageRegions = $($ExtnInfoXml.ExtensionInfo.CloudTypes.$($CloudName).SDPRegions.$nextStage)
            IfNullThrowAndExit -inputObject $NextStageRegions -ErrorMessage "Stage $($nextStage) in $($CloudName) is not valid."

            if($NextStageRegions.Length -le $ExtnRegions.Length)
            {
                ThrowAndExit -ErrorMessage "Regions in $($nextStage) must be more than $($stageName) in Cloud '$($CloudName)'."
            }

            if($NextStageRegions -notmatch $ExtnRegions)
            {
                ThrowAndExit -ErrorMessage "Regions in $($nextStage) must include the regions in $($stageName) in Cloud '$($CloudName)'."
            }
        }
    }
}

# =================================================================================================
# Main execution 
# =================================================================================================
# remove any extra \ at the end. This will cause errors in file paths
$outputDir = $outputDir.TrimEnd('\')

# Create the EV2 folder structure
$ServiceGroupRoot = Create-DeploymentFolder -rootPath $outputDir -subdirectory 'ServiceGroupRoot'
$Param_path = Create-DeploymentFolder -rootPath $ServiceGroupRoot -subdirectory 'Parameters'
$Template_path = Create-DeploymentFolder -rootPath $ServiceGroupRoot -subdirectory 'Templates'

$ExtensionInfoFileName = Split-Path -Path $ExtensionInfoFile -Leaf

$ExtensionInfoXmlContent = New-Object xml
$ExtensionInfoXmlContent = [xml](Get-Content $ExtensionInfoFile -Encoding UTF8)

# Validate the XML file
Validate-ExtensionInfoFile -ExtnInfoXml $ExtensionInfoXmlContent

# Add build version file. This is the build version and Not Extension version
if(!$BuildVersion)
{
    $BuildVersion = "1.0.0.0"
}
$buildVersionFile = Join-Path -Path $ServiceGroupRoot -ChildPath 'BuildVer.txt'
$BuildVersion | Out-File $buildVersionFile -Encoding utf8 -Force

# Generate the Parameter file
$paramsFileName = 'ArmParameters.json'
$ParameterFile = Join-Path $Param_path -ChildPath $paramsFileName
[string] $Parameter_Template_File = Get-ParameterFileTemplate
$Parameter_Template_File | Out-File $ParameterFile -Encoding utf8 -Force

# Generate the Template file
$void = Get-TemplateFile -TemplateFilePath $Template_path -TemplateFileName "UpdateConfig.Template.json"

foreach ($CloudType in $ExtensionInfoXmlContent.ExtensionInfo.CloudTypes.ChildNodes)
{
    $CloudName =  $CloudType.Name

    Get-RolloutParameterFile -ServiceGroupRoot "$($ServiceGroupRoot)" -CloudName $CloudName -ExtnInfoXml $ExtensionInfoXmlContent -ReplaceBuildVersionInFileName $ReplaceBuildVersionInFileName -BuildVersion $BuildVersion -UseBuildVersionForExtnVersion $UseBuildVersionForExtnVersion

    Get-ServiceModelFile -ServiceGroupRoot $ServiceGroupRoot -CloudName $CloudName -ExtnInfoXml $ExtensionInfoXmlContent

    Get-AllRolloutSpecFiles -ServiceGroupRoot $ServiceGroupRoot -CloudName $CloudName -ExtnInfoXml $ExtensionInfoXmlContent -UseBuildVersionForExtnVersion $UseBuildVersionForExtnVersion -BuildVersion $BuildVersion
}
