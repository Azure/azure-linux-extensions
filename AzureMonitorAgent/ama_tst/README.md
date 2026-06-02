# Troubleshooting Tool for Azure Monitor Linux Agent
The following document provides quick information on the AMA Troubleshooting Tool, including how to use it and its checks.

# Table of Contents
- [Troubleshooter Basics](#troubleshooter-basics)
- [Using the Troubleshooter](#using-the-troubleshooter)
- [Requirements](#requirements)
- [Scenarios Covered](#scenarios-covered)
- [Release](#release)

## Troubleshooter Basics

The Azure Monitor Linux Agent Troubleshooter is designed in order to help find and diagnose issues with the agent, as well as general health checks. At the current moment, the AMA TST can run checks to verify agent installation, connection, and general heartbeat, as well as collect AMA-related logs automatically from the affected Linux VM. In addition, more checks are being added regularly, to help increase the number of scenarios the AMA TST can catch.

## Using the Troubleshooter

The AMA Linux Troubleshooter is automatically installed upon installation of AMA, and can be located and run by the following commands:
1. Go to the troubleshooter's installed location: `cd /var/lib/waagent/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<version>/ama_tst`
2. Run the troubleshooter: `sudo sh ama_troubleshooter.sh`

If the troubleshooter isn't properly installed, or needs to be updated, the newest version can be downloaded from the project's [GitHub Releases](https://github.com/Azure/azure-linux-extensions/releases?q=ama_tst&expanded=true) page and run by following the steps below.

1. Download the latest troubleshooter bundle from GitHub Releases:
    ```bash
    if command -v gh >/dev/null 2>&1; then
        gh release download $(gh release list --repo Azure/azure-linux-extensions --limit 100 --json tagName -q 'map(select(.tagName | startswith("ama_tst-"))) | .[0].tagName') \
            --repo Azure/azure-linux-extensions --pattern 'ama_tst-*.tgz' --output ama_tst.tgz
    else
        curl -sSL "$(curl -sSL "https://api.github.com/repos/Azure/azure-linux-extensions/releases?per_page=100" \
            | grep -oE '"browser_download_url": *"[^"]*ama_tst-[^"]*\.tgz"' \
            | head -n1 | cut -d'"' -f4)" -o ama_tst.tgz
    fi
    ```
2. Unpack the bundle: `tar -xzvf ama_tst.tgz`
3. Run the troubleshooter: `sudo sh ama_tst/ama_troubleshooter.sh`

## Requirements

The AMA Linux Troubleshooter requires Python 2.6+ installed on the machine, but will work with either Python2 or Python3. In addition, the following Python packages are required to run (all should be present on a default install of Python2 or Python3):
| Python Package | Required for Python2? | Required for Python3? |
| --- | --- | --- |
| copy | **yes** | **yes** |
| datetime | **yes** | **yes** |
| json | **yes** | **yes** |
| os | **yes** | **yes** |
| platform | **yes** | **yes** |
| re | **yes** | **yes** |
| requests | no | **yes** |
| shutil | **yes** | **yes** |
| subprocess | **yes** | **yes** |
| urllib | **yes** | no |
| xml.dom.minidom | **yes** | **yes** |

## Scenarios Covered

1. Agent having installation issues
    * Supported OS / version
    * Available disk space
    * Package manager is available (dpkg/rpm)
    * Submodules are installed successfully
    * AMA installed properly
    * Syslog available (rsyslog/syslog-ng)
    * Using newest version of AMA
    * Syslog user generated successfully
2. Agent doesn't start, can't connect to Log Analytics
    * AMA parameters set up
    * AMA DCR created successfully
    * Connectivity to endpoints
    * Submodules started
    * IMDS/HIMDS metadata and MSI tokens available
3. Agent is unhealthy, heartbeat doesn't work properly
    * Submodule status
    * Parse error files
4. Agent has high CPU / memory usage
    * Check logrotate
    * Monitor CPU/memory usage in 5 minutes (interaction mode only)
5. Agent syslog collection doesn't work properly
    * Rsyslog / syslog-ng set up and running
    * Syslog configuration being pulled / used
    * Syslog socket is accessible
6. Agent custom log collection doesn't work properly
    * Custom log configuration being pulled / used
    * Log file paths is valid
7. Agent metrics collection doesn't work properly
    * Runs the metrics troubleshooter script
    * Produces `MdmDataCollectionOutput_*.tar.gz` for investigation
8. (A) Run all scenarios
    * Run through scenarios 1-7 in order
9. (L) Collect logs
    * Collects all of the logs needed to troubleshoot AMA in a zip file
    * Includes MDSD and AMACoreAgent environment variables

## Release

Release versioning and naming convention:
- Tag: `ama_tst-<version>` (e.g. `ama_tst-1.7`)
- Release title: `AMA Troubleshooter v<version>` (e.g. `AMA Troubleshooter v1.7`)
- Asset: `ama_tst-<version>.tgz` (e.g. `ama_tst-1.7.tgz`)

The single source of truth for the version is the `TST_VERSION` variable in [`ama_troubleshooter.sh`](./ama_troubleshooter.sh).

### Step-by-step

1. Merge any feature/fix PRs into `master`.
2. Open a one-line PR bumping `TST_VERSION="X.Y"` in `AzureMonitorAgent/ama_tst/ama_troubleshooter.sh`, get it reviewed, and merge to `master`.
3. From a fresh checkout of `master`, run the script below to build the archive and publish the release.

### Scripted release

The `AzureMonitorAgent/ama_tst/release.sh` script handles steps 3 onward. It reads the version directly from `ama_troubleshooter.sh`, builds a clean `.tgz` from the tip of `master` via `git archive` (so untracked files are never included), and uses the [GitHub CLI](https://cli.github.com/) (`gh`) to create the tagged release and upload the asset.

Usage:
```bash
# From the root of your azure-linux-extensions clone, after the version bump has merged:
bash AzureMonitorAgent/ama_tst/release.sh "Added Debian 13 support for x86_64 and aarch64"
```

### Verification

After the script finishes:
- Confirm the release page renders correctly: `https://github.com/Azure/azure-linux-extensions/releases/tag/ama_tst-<version>`
- Confirm the asset is downloadable via the documented [install steps](#using-the-troubleshooter):
  ```bash
  gh release download --repo Azure/azure-linux-extensions --pattern 'ama_tst-*.tgz' --output /tmp/ama_tst.tgz \
      && tar -tzvf /tmp/ama_tst.tgz | head
  ``
