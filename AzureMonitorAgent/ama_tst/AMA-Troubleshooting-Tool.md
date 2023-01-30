# Troubleshooting Tool for Azure Monitor Linux Agent
The following document provides quick information on how to install the Troubleshooting Tool, as well as some common error codes.

**Note that the Troubleshooting Tool can only collect logs currently, but scenarios will be added in the future.**

# Table of Contents
- [Troubleshooter Basics](#troubleshooter-basics)
- [Using the Troubleshooter](#using-the-troubleshooter)
- [Requirements](#requirements)
- [Scenarios Covered](#scenarios-covered)

## Troubleshooter Basics

The Azure Monitor Linux Agent Troubleshooter is designed in order to help find and diagnose issues with the agent, as well as general health checks. At the current moment, the AMA TST can run checks to verify agent installation, connection, and general heartbeat, as well as collect AMA-related logs automatically from the affected Linux VM. In addition, more checks are being added regularly, to help increase the number of scenarios the AMA TST can catch.

## Using the Troubleshooter

The AMA Linux Troubleshooter is automatically installed upon installation of AMA, and can be located and run by the following commands:
1. Go to the troubleshooter's installed location: `cd /var/lib/waagent/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<version>/ama_tst`
2. Run the troubleshooter: `sudo sh ama_troubleshooter.sh`

If the troubleshooter isn't properly installed, or needs to be updated, the newest version can be downloaded and run by following the steps below.

1. Copy the troubleshooter bundle onto your machine: `wget https://github.com/Azure/azure-linux-extensions/raw/master/AzureMonitorAgent/ama_tst/ama_tst.tgz`
2. Unpack the bundle: `tar -xzvf ama_tst.tgz`
3. Run the troubleshooter: `sudo sh ama_troubleshooter.sh`

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
4. (PLANNED) Agent performance counter collection doesn't work properly
5. (PLANNED) Agent has high CPU / memory usage
6. (PLANNED) Agent syslog collection doesn't work properly
7. (PLANNED) Agent custom log collection doesn't work properly
8. (A) Run all scenarios
	* Run through scenarios 1-7 in order
9. (L) Collect logs
	* Collects all of the logs needed to troubleshoot AMA in a zip file
