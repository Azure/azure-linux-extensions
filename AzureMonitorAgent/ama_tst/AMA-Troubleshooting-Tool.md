# Troubleshooting Tool for Azure Monitor Linux Agent
The following document provides quick information on how to install the Troubleshooting Tool, as well as some common error codes.

**Note that the Troubleshooting Tool can only collect logs currently, but scenarios will be added in the future.**

# Table of Contents
- [Troubleshooter Basics](#troubleshooter-basics)
- [Using the Troubleshooter](#using-the-troubleshooter)
- [Requirements](#requirements)
- [Scenarios Covered](#scenarios-covered)

## Troubleshooter Basics

The Azure Monitor Linux Agent Troubleshooter currently can collect logs on a VM running AMA Linux.

## Using the Troubleshooter

The AMA Linux Troubleshooter can be downloaded and run by following the steps below.

1. Copy the troubleshooter bundle onto your machine: `wget https://github.com/Azure/azure-linux-extensions/raw/master/AzureMonitorAgent/ama_tst/ama_tst.tgz`
2. Unpack the bundle: `tar -xzvf ama_tst.tgz`
3. Run the troubleshooter: `sudo sh ama_troubleshooter.sh`

## Requirements

The AMA Linux Troubleshooter requires Python 2.6+ installed on the machine, but will work with either Python2 or Python3. In addition, the following Python packages are required to run:
| Python Package | Required for Python2? | Required for Python3? |
| --- | --- | --- |
| datetime | **yes** | **yes** |
| os | **yes** | **yes** |
| platform | **yes** | **yes** |
| shutil | **yes** | **yes** |
| subprocess | **yes** | **yes** |

## Scenarios Covered

** Currently the AMA Troubleshooting Tool can only collect logs; however, more scenarios are coming in the future.**
