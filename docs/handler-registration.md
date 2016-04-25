# Handler Registration

In this page, we will show you the steps to package and register your extensions to Azure repository. We assume that you have prepared your `SampleExtension` in `~/azure-linux-extensions/`.

For registering a handler the following two components are required:

* the handler package - The extension handler package needs to be uploaded to a storage location.
* the definition xml file - This section gives an overview of some of the key elements that are required in the definition file.

Also, the extension should be registered under the Publisher’s Azure Subscription. Prior to Registration, the subscription should be approved for publishing by Azure Runtime team. During the handler registration, you need specify the certificate of your Azure subscription.

We provide some scripts to help package and register your extensions.

```
registration-scripts/
├── api
│   ├── add-extension.sh
│   ├── check-request-status.sh
│   ├── del-extension.sh
│   ├── get-extension.sh
│   ├── get-subscription.sh
│   ├── list-extension.sh
│   ├── params
│   └── update-extension.sh
├── bin
│   ├── add.sh
│   ├── blob
│   │   ├── list.sh
│   │   └── upload.sh
│   ├── check.sh
│   ├── del.sh
│   ├── get.sh
│   ├── list.sh
│   ├── subscription.sh
│   └── update.sh
├── create_zip.sh
├── mooncake
│   └── sample-extension-1.0.xml
└── public
    └── sample-extension-1.0.xml
```

<a name="package-and-upload-your-extension"/>
## Package and upload your extension

You can package your extension into a zip file using the following command.

```
cd ~/azure-linux-extensions/
./registration-scripts/create_zip.sh SampleExtension/ 1.0.0.0
```

Then you will get `SampleExtension-1.0.0.0.zip` in `build` directory.

You should upload your extension to a downloadable storage, for e.g. [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/).

```
bin/blob/upload.sh ~/azure-linux-extensions/build/SampleExtension-1.0.0.0.zip
```

<a name="register-your-extension"/>
## Register your extension

### Prepare your subscription for registration

The extension should be registered under the Publisher’s Azure Subscription.

### How to use the publish scripts

The following scripts are executed in `registration-scripts` directory.

You can configure `api/params` to change the endpoint (Public Azure or Mooncake).

### Definition File

For registration, the publisher would have to provide the definition file.

| Property | Description | Requirements |
|:---------------:|:----- |:----- |
| ProviderNamespace | This has to be a unique namespace per each subscription. The namespace is a combination of company team, team name (optional) and product name. E.g.: Microsoft.Azure.RemoteAcccess | Namespace cannot be empty, should be less than 256 chars and underscores cannot be used. |
| Type | Name of the Extension Handler. The type indicate the purpose of the extension | Type cannot be empty, should be less than 256 chars and underscores cannot be used. |
| Version | Version number of the handler. The combination of namespace, type and version uniquely identifies an extension. | The version number needs to be changed for every release. The format of version number has to be `<major>.<minor>.<build>.<revision>` Eg: 1.0.1.1 |
| Label | The label of the extension | |
| HostingResource | This should be either WebRole or WorkerRole or VmRole depending on whether it’s targeted for PaaS or IaaS. | These values are case sensitive. |
| MediaLink | The blob url which has the Extension Package. | MediaLink value must point to a URL(either Http or Https) in a blob storage and is downloadable. |
| Description | The description of the extension | |
| IsInternalExtension | If this is set to "true", the handler is not visible for public use. It can be still accessed by referring to the Namespace, Type & Version combo. | Possible values are case-sensitive true or false |
| Eula | If the software requires any additional EULAs, a link to the EULA should be provided. | |
| PrivacyUri | If the software collects any data and transfers out the VM, then a additional Privacy document might be needed. | |
| HomepageUri | A public URL that has usage information and contact information for customer support. | |
| IsJsonExtension | Whether the Extension configuration is json format | It should always be "true". |
| SupportedOS | The supported OS | It should always be "Linux". |
| CompanyName | The company name | |

You can prepare your sample definition file `public/sample-extension-1.0.xml`.

```
<ExtensionImage xmlns="http://schemas.microsoft.com/windowsazure">
<ProviderNameSpace>Microsoft.Love.Linux</ProviderNameSpace>
<Type>SampleExtension</Type>
<Version>1.0.0.0</Version>
<Label>Microsoft loves Linux</Label>
<HostingResources>VmRole</HostingResources>
<MediaLink>Storage blob location of the Zip file</MediaLink>
<Description>Microsoft loves Linux</Description>
<IsInternalExtension>false</IsInternalExtension>
<Eula>https://github.com/Azure/azure-linux-extensions/blob/1.0/LICENSE-2_0.txt</Eula>
<PrivacyUri>https://github.com/Azure/azure-linux-extensions/blob/1.0/LICENSE-2_0.txt</PrivacyUri>
<HomepageUri>https://github.com/Azure/azure-linux-extensions</HomepageUri>
<IsJsonExtension>true</IsJsonExtension>
<SupportedOS>Linux</SupportedOS>
<CompanyName>Microsoft</CompanyName>
</ExtensionImage>
```

### Register the new extension

```
bin/add.sh public/sample-extension-1.0.xml
```

The operation of registration and unregistration is asynchronous. You can check the status of the operation using the following command.

```
bin/check.sh <x-ms-request-id>
```

You can get `<x-ms-request-id>` from the output of the registration operation.

### Update your extension

Once the extension is published, any changes to the handler can be published as newer versions, using the update API.

```
bin/update.sh public/sample-extension-1.0.xml
```

Here is an overview of updates are done:

* **Hotfixes** - Publisher should release hotfixes by changing the revision number. Eg: If the current version is 1.0.0.0, then the hotfixed version would be 1.0.0.1. All hotfixes would be automatically installed on the VM.
* **Minor Version Changes** - Any minor features can be released as a minor update. E.g.: If the current version is 1.0.0.0, then a minor version update would be 1.1.0.0.
If the client opts in for auto upgrade, all minor version changes would be automatically applied.
* **Major Version Change** - Any breaking changes in the handler should be released as a major version update. The client has to explicitly request the major version changes.

### List your extensions

**NOTE:** After registration and updating, you need to wait some time to **replicate** your extension. The wait time depends on the work load of the replication system, from half an hour to one day.

You can get the replication status of the extension using the following command:

```
bin/list.sh
```

### Unregister your extension

```
bin/delete.sh <ProviderNameSpace> <Type> <Version>
```

Sample:

```
bin/delete.sh Microsoft.Love.Linux SampleExtension 1.0.0.0
```

**NOTE:** Unregistration is supported for internal extensions only. You need to update your extension from public into internal before unregistration.
