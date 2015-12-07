# Design Details

This page descibes the design details of the extension. You can write an extension from scrach folloing this page.

<a name="handler-artifacts"/>
## Handler Artifacts

An Azure Extension Handler is composed of the following artifacts:

1. **Handler Package**: This is the package that contains your Handler binary files and all standard static configuration files. This package is registered with the Azure ecosystem.

2. **Handler Environment**: This is the set of files and folders that WALA sets up for the Handlers to use at runtime. These files can be used for communicating with WALA (heartbeat and status) or for writing debugging information (logging). The details of handler environment created by WALA is discussed in the section [Handler Environment](#handler-environment).

3. **Handler Configuration**: This is a configuration file that contains various settings needed to configure this Handler at runtime. Extension configuration is the input provided by the end user based on the schema provided by the handler publisher during registration. For example, a handler might get the client authentication details for writing logs to his storage account via the handler configuration.

<a name="handler-package"/>
### Handler Package

The Handlers are packaged as simple zip files for being registered in the Azure ecosystem. The zip file is supposed to contain the following:

* The handler binaries.
* HandlerManifest.json file that is used by WALA to manage the handler. This HandlerManifest.json file should be located in the root folder of the zip file.

  The JSON file should be of the format:

  ```
  [{
    "version": 1.0,
    "handlerManifest": {
      "installCommand": "<your install command>",
      "uninstallCommand": "<your uninstall command>",
      "updateCommand": "<your update command>",
      "enableCommand": "<your enable command>",
      "disableCommand": "<your disable command>",
      "rebootAfterInstall": <true | false>,
      "reportHeartbeat": <true | false>
    }
  }]
  ```

  The above JSON file provides a list of all commands that will be executed by WALA for managing various handlers on the VM.

  * **Version**: indicates the version of the protocol which should be used by WALA to deserialize this JSON. 

  * **Install\Uninstall\Update\Enable\Disable** point to the command line that will be executed by WALA in various scenarios. The paths of the command line provided in HandlerManifest.json should be relative to the root directory of the handler. The current working directory of the handler is the path of the root folder of the handler. All these command lines are launched as LOCAL SYSTEM with administrative privileges.   

    **Note**: It is valid for multiple commands in the HandlerManifest to point to the same command line. For e.g. the install and Update command might point to the same binary with same parameters.

  * **RebootAfterInstall** notifies WALA if a reboot is required to complete the installation of a handler. Handlers should not reboot the system independently to avoid interfering with each other. 

  * **ReportHearbeat** indicates WALA if the handler will be reporting heartbeat or not. The details of heartbeat and status is discussed in section [Heartbeat Reporting](#heartbeat_reporting).

  **Note:** All of the fields in the JSON specified above are required fields and registration of the handler with Azure will fail if one of these fields in not specified. The explanation of the meaning of various fields in the JSON with respect to WALA is provided in the below sections.

  An example of the directory structure of the zip file for a handler is:

  ```
  SampleExtension.zip
      |-HandlerManifest.json
      |-install.py
      |-uninstall.py
      |-enable.py
      |-disable.py
      |-update.py
  ```

  A sample HandlerManifest.json for the above sample handler would be:

  ```
  [{
    "version": 1.0,
    "handlerManifest": {
      "installCommand": "./install.py",
      "uninstallCommand": "./uninstall.py",
      "updateCommand": "./update.py",
      "enableCommand": "./enable.py",
      "disableCommand": "./disable.py",
      "rebootAfterInstall": false,
      "reportHeartbeat": true
    }
  }]
  ```

<a name="handler-environment"/>
### HandlerEnvironment

When WALA installs a handler on the VM, it creates a bunch of files and folders that are needed by the handler at runtime for various purposes. The location of all these files and folders are communicated to the handler via the HandlerEnvironment.json file.

HandlerEnvironment.json is the file that is created under the root directory where the handler is unpackaged. The structure of HandlerEnvironment.json is:

  ```
  [{
    "version": 1.0,
    "handlerEnvironment": {
      "logFolder": "<your log folder location>",
      "configFolder": "<your config folder location>",
      "statusFolder": "<your status folder location>",
      "heartbeatFile": "<your heartbeat file location>",
    }
  }]
  ```

  * **version** - contains the version of the protocol that WALA is abiding with. In the initial release the only supported version is 1.0.

  * **handlerEnvironment** – This is the object that encapsulates all the properties of a handler defined in the version 1.0 of the protocol.

  * **logFolder** – contains the location where the handler should put its log files that might be needed to debug any customer issues. The advantage of putting log files under the folder directed by this location is that these files can be automatically retrieved from the customers VM by using a tool, without actually logging into the VM and copying them over manually.

  * **configFolder** – contains the location where the handler will get its configuration settings file. 

  * **statusFolder** – contains the location where the handler is supposed to write back a file with a structured status of the current state of the work being done by the handler.

  * **heartbeatFile** - this is the file that is used to communicate the heartbeat of the handler back to WALA.

Errors while reading HandlerEnvironment.json – In rare cases a handler might encounter errors when trying to read the HandlerEnvironment.json file, since WALA might be writing the file at the same time as well. The handler should be capable of handling such errors. Our recommendation for handler publishers would be to have a retry logic with some sort of backoff.

<a name="handler-configuration"/>
### Handler Configuration

There are scenarios when a handler needs some user input parameters to configure its handler. All such user provided input is communicated from WALA to the handler via the configuration file. For e.g. a handler might require the user to provide the account name and the key of a user storage account where the logs will be saved. This account information can be passed by the user to the handler via the configuration file.

#### Configuration File Structure

The configuration file should be a valid JSON with the only property of the root object as `handlerSettings` and with two child objects `protectedSettings` and `publicSettings`. Apart from that the complete schema of the handler configuration file under the `publicSettings`\`protectedSettings` property is defined by the handler publisher during the registration process. When a call to add the handler to the VM is made, the user needs to provide a configuration that complies with the structure that the handler publisher had provided during registration. 

**Managing user secrets**: There may be parts of the handler configuration that contain user secrets (like passwords, storage keys, etc). These secrets in general should never be persisted in plain text to prevent accidently disclosure. To support this concept, the Azure Extension Handler publishers can allow users to store all or part of the handler configuration in a protected section of the config. All settings under this section are encrypted by an X509 certificate before being sent over to the VM. The WALA will persist the protected settings as encrypted only and will provide the thumbprint of the certificate that needs to be used for decrypting this information. To extract the setting, the handler will need to retrieve the certificate from the Local Machine store and decrypt the settings using the certificate private key. The publisher of the Azure Extension Handler decides what, if any, part of the configuration should be protected in this manner.

A sample configuration file would look like:

```
{
  "handlerSettings": {
    "protectedSettings": {
      "storageaccountname": "MY SECRET STORAGE ACCOUNT NAME",
      "storageaccountkey": "MY SECRET STORAGE ACCOUNT KEY"
    },
    "publicSettings": {
      "MyHandlerConfiguration": {
        "configurationChangePollInterval": " ",
        "overallQuotaInMB": 12
      },
      "MyHandlerInfrastructureLogs": {
        "scheduledTransferLogLevelFilter": "Verbose",
        "bufferQuotaInMB": "100",
        "scheduledTransferPeriod": "PT1M"
      }
    }
  }
}
```

In the above example the storageaccountname and storageaccountkey are protected secrets. When these secrets are persisted on a file in the VM for consumption by the handler the protected section would be encrypted and base64 encoded. In the case of above settings, the configuration file for the above sample on the VM would look like:

```
{
  "handlerSettings": {
    "protectedSettingsCertThumbprint": "a811c3f4058542418abb",
    "protectedSettings": "ICB7DQogICAgInN0b3JhZ2VhY2NvdW50IiA6ICJbcGFyY
                          W1ldGVycy5TdG9yYWdlQWNjb3VudF0iLA0KICB9LA0K",
    "publicSettings": {
      "DiagnosticMonitorConfiguration": {
        "configurationChangePollInterval": " ",
        "overallQuotaInMB": 12
      },
      "DiagnosticInfrastructureLogs": {
        "scheduledTransferLogLevelFilter": "Verbose",
        "bufferQuotaInMB": "100",
        "scheduledTransferPeriod": "PT1M"
      }
    }
  }
}
```

<a name="location-of-handler-configuration"/>
#### Location of Handler Configuration

The location where the configuration setting files will be written can be retrieved by the "configFolder" property in the HandlerEnvironment.json file.

<a name="handler-configuration-filename"/>
#### Handler Configuration Filename

Whenever a new configuration is received, WALA will write the configuration settings file named <SequenceNumber>.settings under the configFolder with the configuration provided by the user and launches [the enable command of the handler](#enable). 

The handler is expected to retrieve the last sequence number of the configuration file written by WALA bylooking under the configfolder directory for the highest sequence number. This sequence number can then be used to apply the latest user provided configuration settings to the handler.

## Handler Lifecycle management

### Add a new handler on the VM (Install and Enable)

When a handler is requested on a VM by the user, WALA will do the following inside the VM:

1. Download the handler package zip from Azure repository to `/var/lib/waagent`.
2. Unzip the package under a unique location corresponding to the handler identity. The handler should not take any dependency on the location where the handler package is unpacked, since this location might change in future depending on future requirements. Currently, the unique location is formatted as `<ProviderNamespace>.<Type>-<Version>`. 
3. Create the configuration, logging and status folders for the handler.
4. Create the <SequenceNumber>.settings file with the initial configuration.
5. Creates the HandlerEnvironment.json file under the root folder where the handler is unpacked.
6. Parse the HandlerManifest.json file and execute the install command in a separate process.
7. The install command is executed in the process with the root privileges.
8. If there are multiple handlers that are being installed, WALA will download and unzip them in parallel but will invoke the install command sequentially only. 
9. WALA will wait for the installation to complete and monitor the exit code of the install process.
10. If the install process exits **SUCCESSFULLY** (exit code 0), WALA maintains state that the handler was installed successfully and does not run the install command for the same handler again ever unless the handler has been uninstalled first.
  * WALA will wait for a maximum of 5 minutes before timing out the install process and considering the install to be failed.
11. If the install process exits **SUCCESSFULLY**, WALA will provide the handler configuration settings in the defined location and launch the `Enable` command in a separate process that runs with root privileges.
12. If the install process exits **UNSUCCESSFULLY**, WALA will retry to install the handler under two circumstances:
  * When WALA receives a new goal state triggered by a user action. (e.g. Adding\removing\updating any handler or updating handler configuration etc.)
  * When WALA restarts (which should only happen when the machine itself is rebooted).

#### Install command

In the install command, the handler is expected to install its processes and services on the system and create the necessary setup that is required for the handler to run at runtime. 

### Remove a handler from the VM (Disable and Uninstall)

When a user explicitly requests to remove the handler from the VM, WALA will execute the following actions:

1. The disable command specified in the HandlerManifest.json will be executed in a separate process that runs with root privileges. The handler is expected to complete the pending tasks and then stop any processes or services related to the handler that have been running on the machine.
  * WALA will wait for a max of 5 minutes for the disable process to finish before timing out to the next steps.
2. The uninstall command will be invoked in a separate process that runs with root privileges. WALA will wait for a maximum of 5 mins for the uninstall process to finish.
3. WALA will remove all the package binaries and configuration files that were associated with the handler. The handler log files will be maintained on the machine for any future debugging purposes.

### Disable

A user might explicitly request to disable a handler without uninstalling it. On disable WALA will execute the disable command in a separate process with root privileges. On the execution of the disable command the handler is expected to complete the pending tasks and then stop any processes or services related to the handler that have been running on the machine.

WALA will wait a max of 5 mins for the disable process to finish before timing out to the next steps.

### Enable

A user might explicitly request to enable a handler that has been previously disabled. On enable WALA will execute the enable command in a separate process with root privileges.

The enable command will be invoked every time the machine reboots or the machine receives a new configuration settings file. 

**Note:**
Unlike the install state, WALA will not maintain the enabled\disabled state of the handler. Every time the machine restarts (which in turn will restart WALA) or a new goal state is received, WALA will try to set the machine to the latest goal state. Thus it might invoke the enabled\disabled commands multiple times even if the handler is already enabled\disabled. So the enable and disable commands need to be idempotent i.e. if the handler is already enabled and the enable command is invoked again, the command should check if all the processes are running as expected, if yes, then the command should just exit with a success code. 

### Update

There are two scenarios when an update can happen:
* The user triggers an explicit update of the handler.
* The handler is updated on Azure repository and it automatically gets picked up by WALA.

In both these cases WALA will identify that a handler with the same name and publisher and a lower version is already installed on the machine. 

1. It will download the updated version of the handler from Azure repository, unpack it under the handler identity folder.
2. WALA will call disable on the existing handler with the lower version.
3. WALA will invoke the update command in the newly downloaded packages under a separate process with root privileges. During update the handler has an opportunity to transfer any state information from the previous handler.
4. WALA will invoke the uninstall command on the existing handler with lower version.
5. WALA will invoke the enable command on the newly downloaded package

<a name="reporting-status-and-heartbeat"/>
## Reporting Status and Heartbeat

Microsoft Azure provides two facilities to report back the health of the handler and the status of the operations being performed by it.

1. **Heartbeat**: Heartbeat channel should be used to report the health of the handler itself. Providing heartbeat is an optional facility that the handler can opt into by setting the reportHearbeat property to true in the HandlerManifest. Heartbeat is generally expected to be reported by long running services or processes. For e.g. an antivirus handler service might use the heartbeat channel to indicate if its service has stopped for some reason.

2. **Configuration Status**: Status channel should be used to report the success or failures of any operations that were conducted when applying the new configuration provided by the user. For e.g. Diagnostics agent might report issues connecting to the storage account via this channel. 
The WALA collects the heartbeat and status information for all handlers and aggregates them into VM health which is returned to the user when he queries for it via the GetDeployment RDFE API call.

### Heartbeat reporting

The handler that have opted into reporting heartbeat are supposed to report it via the file specified in the heartbeat property of the HandlerEnvironment file. The structure of the heartbeat file should be:

```
[{
    "version": 1.0,
    "heartbeat" : {
        "status": "<ready | notready>",
        "code": <Valid integer status code>,
        "Message": "<Human readable information or error message passed to the user>"
    }
}]
```

Various fields in the above JSON document correspond to the following:
* **Version** – This is the version of the protocol being used to communicate heartbeat to WALA. Currently the only version WALA understands is 1.0.
* **Heartbeat** – This object encapsulates all the heartbeat related information for the handler.
* **Status** – The current status of the handler. The only valid values are “ready” and “notready”.
* **Code** – The status code the handler. This is an optional field.
* **Message** – A human readable\actionable error message for the user. This is an optional field. 

Handlers can report successful heartbeat by setting the status to "ready". To report repeated successful heartbeats, the handler can just change the last modified timestamp of this file. The status field only needs to be changed to "notready" if the handler has encountered some error\exception condition while executing. For e.g. If after the handler is installed and before the first configuration settings file is processed, if there is an exception, it can be reported via the status section in the heartbeat file.

WALA will read the heartbeat file once every 2 minutes to check if the plugin is running or not. If the last modified timestamp is within the last 1 minute and the status is set to "ready" then WALA will consider the plugin to be working properly. If the last modified timestamp is older than 10 minutes, WALA will consider the plugin handler to be unresponsive. If the last modified timestamp is between 1 minute and 10 minute, WALA will consider the plugin to be in "Unknown" state. If the status is set to "NotReady", the error code and the message will be returned back to the user in the next GetDeployment call. 

A sample heartbeat file would look like:

```
[{
    "version": 1.0,
    "heartbeat" : {
        "status": "ready",
        "code": 0,
        "Message": "Sample Handler running. Waiting for a new configuration from user."
    }
}]
```

Errors while writing to the HeartBeat file – In rare cases a handler might encounter errors when trying to write the heartbeat file, since WALA might be reading the file at the same time as well. The handler should be capable of handling such errors. Our recommendation for handler publishers would be to have a retry logic with some sort of exponential backoff.

### Status reporting

The handler can report status back to WALA by writing to the status file "<SequenceNumber>.status" under the status folder specified in the HandlerEnvironment. The status file structure supported by WALA is:

```
[{
    "version": 1.0,
    "timestampUTC": "<current utc time>",
    "status" : {
        "name": "<Handler workload name>",
        "operation": "<name of the operation being performed>",
        "configurationAppliedTime": "<UTC time indicating when the configuration was last successfully applied>",
        "status": "<transitioning | error | success | warning>",
        "code": <Valid integer status code>,
        "message": {
            "id": "id of the localized resource",
            "params": [
                "MyParam0",
                "MyParam1"
            ]
        },
        "formattedMessage": {
            "lang": "Lang[-locale]",
            "message": "formatted user message"
        },
        "substatus": [{
            "name": "<Handler workload subcomponent name>",
            "status": "<transitioning | error | success | warning>",
            "code": <Valid integer status code>,
            "Message": {
            		"id": "id of the localized resource",
            		"params": [
                		"MyParam0",
                		"MyParam1"
            		]
        	},
      	  	"FormattedMessage": {
            		"Lang": "Lang[-locale]",
            		"Message": "formatted user message"
        	},        
        }]
    }
}]
```

* **version** – indicates the version of the protocol being used for communicating the status back to WALA.
* **timestampUTC** – The current time in UTC during which this status structure is being created.
* **status** – The object that encapsulates the top level status about the configuration corresponding to what the status is being reported.
* **status\name** – This property is optional. This property can be used by handlers to point to the VM workload name that are being managed by the handler.
* **status\operation** – This property is optional. This property can be used by handlers to indicate the current operation being performed to enable the VM workload on the machine.
* **status\configurationappliedtime** – This property is optional. This property can be used by handlers to indicate the last time the configuration corresponding to the current sequence number was successfully applied on the VM.
* **status\status** – This property indicates the current status of the operation being performed. The only acceptable values are: Transitioning, error, success and warning.
* **status\code** – A valid integer status code for the current operation.
* **status\message** – This is an optional localized message that will be passed back to the user on a GetDeployment call via RDFE.
* **status\message\id** – This is the message identifier, to be used for lookup of a localized message. Treated as a string. A symbolic id is preferred for human interpretation, for example Error_CannotConnect. The file that contains all the localized strings corresponding to the id would be provided by the handler author to Azure during registration.
* **status\message\params** - This is an Ordered list of parameter (placeholder) values to be filled into the message template corresponding to the message id. The first Param is used for placeholder “{0}” in the message template (from the provided language resources); the second for placeholder “{1}”, etc.
* **status\formattedMessage\lang** - The language/locale of the preformatted message. 
* **status\formattedMessage\message** - The human readable message that will be returned to the user.
* **substatus** – An array of nested substatus objects that can be used by the handler to pass the substatus of complicated operations. The fields in the substatus array are supposed to be used in the same manner as they are used in the parent status array.

Everytime a handler receives a new handler pack via a new configuration, it is expected to periodically report the status corresponding to that configuration in a file names <SequenceNumber.status>. The status should be reported at least once every 2 minutes for the time when the handler is in (transitioning\Warning) state. Once the handler reaches a terminal state (success\error) it can stop reporting the status messages for that sequence number.

Each time the handler has new status to report, it should overwrite <SequenceNumber.status> file. The status provided in the status file should be an aggregate status (even if that status has been reported before) of all the operation performed for this configuration so far. If writing to the file fails, the handler should retry with backoff. The handler can write to the status file whenever it has something new to report. WALA will only read this status file after it has fed a new configuration to the handler and till the time the handler does not report status of a terminal state (success\error). During this time WALA will read the status file with a default frequency of 5 mins (configurable).

A simple status report without localization from a handler would look like:

```
[{
    "version": 1.0,
    "timestampUTC": "2013/11/13, 17:46:30.447",
    "status" : {
        "name": "enable wordpress",
        "operation": "installing wordpress",
        "status": "transitioning",
        "formattedMessage": {
            "Lang": "en",
            "Message": "Enable IIS on the VM."
        },
        "substatus": [{
            "name": "Wordpress plugin",
            "status": "success",
            "code": 0,
	     "formattedMessage": {
            		"Lang": "en",
            		"Message": "Successfully downloaded wordpress plugin."
        	}
        },
        {
            "name": "Enable IIS",
            "status": "transitioning",
            "Message": "Turning windows feature for enabling IIS on."
        }]
    }
}]
```

#### Localization Support

To enable showing these messages in the user’s preferred language and, ideally, to enable multiple users to view the same captured execution status in different languages, we need to defer message resource lookup until the user queries for handler status. The current user’s preferred language would be retrieved from the HTTP header.

Localization support is optional. If the handler does not wish to participate in localization they can just return the FormattedMessage strings in a default language which will be directly returned to the user.

A localized status report would look like:

```
[{
    "version": 1.0,
    "timestampUTC": "<current utc time>",
    "status" : {
        "name": "SharePointFrontEnd",
        "operation": "ResExtProvisioning",
        "status": "error",
        "code": 12,
        "Message": {
            "id": "1215",
            "params": [
                "spo-sqldb.cloudapp.net", "JoeAdmin"
                ]
        }
    }
}]
```

#### Localized message formatting

As part of handler registration with Azure, a set of localization resources will be provided for looking up the status messages from the handler.

A language/locale lookup sequence similar to the one for .NET resources will be applied, with the ultimate fallback being "en", a resource file for which must always be provided.
 
The structure of the JSON resource files will be as follows.

```
[{
    "version": 1.0,
    "lang": "lang[-locale]",
    "messages": [
        {
            "id": "message id",
            "text": "Message text with {0}, {1} placeholder."
        }]
}]
```

**Placeholder ordering** - The order of Status/Param values from the in-guest handler must be fixed (independent of language) and should correspond to the sequence of {n} placeholders in the English version of the message. If translation of a message in some language requires different order of the placeholders, the message template in the resource file for that language should have the placeholders reordered accordingly. To continue the earlier Status sample the message corresponding to id 1215, if in English we have:

  ```
  Failed to establish connection to {0} as {1}
  ```

In German it might be:

  ```
  {1} fehler beim Anschluss an {0} herzustellen
  ```

<a name="logging"/>
# Logging

Handlers should use the folder provided in the "logfolder" property of the handler environment for writing logs required for debugging their handlers in lieu of any issues reported on a live customer VM.
