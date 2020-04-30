<#
.SYNOPSIS
    This script is meant to be called during the CDPx build to replace subscription ID placeholders
    in PublishingSubs.json file. This action needs to be taken before build_ev2_linux.ps1 gets called.
.PARAMETER Clouds
    Mandatory one or more comma separated cloud names (i.e. Public,Fairfax,Mooncake)
.PARAMETER Subs
    Mandatory on or more comma separated subscription IDs matching in order the cloud names.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$Clouds,
    [Parameter(Mandatory=$true)]
    [string]$Subs
)

# transforming input to arrays
$clouds_list = $Clouds.Split(',')
$subs_list = $Subs.Split(',')

# finding the JSON file with placeholder subs
$script_folder = Split-Path -Parent $MyInvocation.MyCommand.Definition
$publishing_subs_path = Join-Path $script_folder "PublishingSubs.json"
$publishing_subs = Get-Content -Path $publishing_subs_path | ConvertFrom-Json

# replacing the placeholders with real subs
for($i = 0; $i -lt $clouds_list.Count; $i++)
{
    $publishing_subs.($clouds_list[$i]) = "$($subs_list[$i])"
}

# saving the PublishingSubs JSON back
$publishing_subs | ConvertTo-Json | Set-Content $publishing_subs_path
