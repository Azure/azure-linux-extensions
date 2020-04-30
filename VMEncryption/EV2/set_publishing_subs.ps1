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

<#
$publishing_subs_path = Join-Path $(Build.SourcesDirectory) "VMEncryption\EV2\PublishingSubs.json"

$publishing_subs = Get-Content -Path $publishing_subs_path | ConvertFrom-Json

$publishing_subs.Public = "$(Public)"
$publishing_subs.Fairfax = "$(Fairfax)"
$publishing_subs.Mooncake = "$(Mooncake)"
$publishing_subs.Blackforest = "$(Blackforest)"

Write-Host $publishing_subs

$publishing_subs | ConvertTo-Json | Set-Content $publishing_subs_path
#>
