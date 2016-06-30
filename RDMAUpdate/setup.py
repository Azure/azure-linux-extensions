#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2015 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# To build:
# python setup.py sdist
#
# To install:
# python setup.py install
#
# To register (only needed once):
# python setup.py register
#
# To upload:
# python setup.py sdist upload

from distutils.core import setup
import os
import json
import subprocess
from zipfile import ZipFile
from main.Common import CommonVariables

packages_array = []
main_folder = 'main'
main_entry = main_folder + '/handle.py'
packages_array.append(main_folder)

patch_folder = main_folder + '/patch'
packages_array.append(patch_folder)

"""
copy the dependency to the local
"""

"""
copy the utils lib to local
"""
target_utils_path = main_folder + '/' + CommonVariables.utils_path_name
packages_array.append(target_utils_path)


"""
generate the HandlerManifest.json file.
"""
manifest_obj = [{
  "name": CommonVariables.extension_name,
  "version": CommonVariables.extension_version,
  "handlerManifest": {
    "installCommand": main_entry + " -install",
    "uninstallCommand": main_entry + " -uninstall",
    "updateCommand": main_entry + " -update",
    "enableCommand": main_entry + " -enable",
    "disableCommand": main_entry + " -disable",
    "rebootAfterInstall": False,
    "reportHeartbeat": False
  }
}]

manifest_str = json.dumps(manifest_obj, sort_keys = True, indent = 4)
manifest_file = open("HandlerManifest.json", "w") 
manifest_file.write(manifest_str)
manifest_file.close()


"""
generate the extension xml file
"""
extension_xml_file_content = """<ExtensionImage xmlns="http://schemas.microsoft.com/windowsazure">
<ProviderNameSpace>Microsoft.OSTCExtensions</ProviderNameSpace>
<Type>%s</Type>
<Version>%s</Version>
<Label>%s</Label>
<HostingResources>VmRole</HostingResources>
<MediaLink>%s</MediaLink>
<Description>%s</Description>
<IsInternalExtension>true</IsInternalExtension>
<Eula>https://github.com/Azure/azure-linux-extensions/blob/1.0/LICENSE-2_0.txt</Eula>
<PrivacyUri>https://github.com/Azure/azure-linux-extensions/blob/1.0/LICENSE-2_0.txt</PrivacyUri>
<HomepageUri>https://github.com/Azure/azure-linux-extensions</HomepageUri>
<IsJsonExtension>true</IsJsonExtension>
<CompanyName>Microsoft Open Source Technology Center</CompanyName>
</ExtensionImage>""" % (CommonVariables.extension_type,CommonVariables.extension_version,CommonVariables.extension_label,CommonVariables.extension_media_link,CommonVariables.extension_description)

extension_xml_file = open(CommonVariables.extension_name + '-' + str(CommonVariables.extension_version) + '.xml', 'w')
extension_xml_file.write(extension_xml_file_content)
extension_xml_file.close()

"""
setup script, to package the files up
"""
setup(name = CommonVariables.extension_name,
      version = CommonVariables.extension_version,
      description=CommonVariables.extension_description,
      license='Apache License 2.0',
      author='Microsoft Corporation',
      author_email='andliu@microsoft.com',
      url='https://github.com/Azure/azure-linux-extensions',
      classifiers = ['Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'License :: OSI Approved :: Apache Software License'],
      packages = packages_array)

"""
unzip the package files and re-package it.
"""
target_zip_file_location = './dist/'
target_folder_name = CommonVariables.extension_name + '-' + str(CommonVariables.extension_version)
target_zip_file_path = target_zip_file_location + target_folder_name + '.zip'

target_zip_file = ZipFile(target_zip_file_path)
target_zip_file.extractall(target_zip_file_location)

def dos2unix(src):
    args = ["dos2unix",src]
    devnull = open(os.devnull, 'w')
    child = subprocess.Popen(args, stdout=devnull, stderr=devnull)
    print('dos2unix %s ' % (src))
    child.wait()

def zip(src, dst):
    zf = ZipFile("%s" % (dst), "w")
    abs_src = os.path.abspath(src)
    for dirname, subdirs, files in os.walk(src):
        for filename in files:
            absname = os.path.abspath(os.path.join(dirname, filename))
            dos2unix(absname)
            arcname = absname[len(abs_src) + 1:]
            print('zipping %s as %s' % (os.path.join(dirname, filename), arcname))
            zf.write(absname, arcname)
    zf.close()

final_folder_path = target_zip_file_location + target_folder_name
zip(final_folder_path, target_zip_file_path)

