#!/usr/bin/env python
#
# Copyright (c) Microsoft Corporation
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

import codecs
import json
import os
import subprocess
from distutils.core import setup
from zipfile import ZipFile
from shutil import copy2

from main.Common import CommonVariables

packages_array = []
main_folder = 'main'
main_entry = main_folder + '/handle.py'
packages_array.append(main_folder)

patch_folder = main_folder + '/patch'
packages_array.append(patch_folder)

oscrypto_folder = main_folder + '/oscrypto'
packages_array.append(oscrypto_folder)

packages_array.append(oscrypto_folder + '/rhel_81')
packages_array.append(oscrypto_folder + '/rhel_81/encryptstates')
packages_array.append(oscrypto_folder + '/91adeOnline')
packages_array.append(oscrypto_folder + '/91ade')
packages_array.append(oscrypto_folder + '/rhel_72_lvm')
packages_array.append(oscrypto_folder + '/rhel_72_lvm/encryptstates')
packages_array.append(oscrypto_folder + '/rhel_72')
packages_array.append(oscrypto_folder + '/rhel_72/encryptstates')
packages_array.append(oscrypto_folder + '/rhel_68')
packages_array.append(oscrypto_folder + '/rhel_68/encryptstates')
packages_array.append(oscrypto_folder + '/centos_68')
packages_array.append(oscrypto_folder + '/centos_68/encryptstates')
packages_array.append(oscrypto_folder + '/ubuntu_1604')
packages_array.append(oscrypto_folder + '/ubuntu_1604/encryptstates')
packages_array.append(oscrypto_folder + '/ubuntu_1404')
packages_array.append(oscrypto_folder + '/ubuntu_1404/encryptstates')
packages_array.append(oscrypto_folder + '/mariner_10')
packages_array.append(oscrypto_folder + '/mariner_10/encryptstates')

six_folder = 'six'
packages_array.append(six_folder)

transitions_folder = 'transitions/transitions'
packages_array.append(transitions_folder)

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
  "version": "1.0",
  "handlerManifest": {
    "installCommand": "extension_shim.sh -c {0} --install".format(main_entry),
    "uninstallCommand": "extension_shim.sh -c {0} --uninstall".format(main_entry),
    "updateCommand": "extension_shim.sh -c {0} --update".format(main_entry),
    "enableCommand": "extension_shim.sh -c {0} --enable".format(main_entry),
    "disableCommand": "extension_shim.sh -c {0} --disable".format(main_entry),
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
<ProviderNameSpace>%s</ProviderNameSpace>
<Type>%s</Type>
<Version>%s</Version>
<Label>%s</Label>
<HostingResources>VmRole</HostingResources>
<MediaLink></MediaLink>
<Description>%s</Description>
<IsInternalExtension>true</IsInternalExtension>
<Eula>https://azure.microsoft.com/en-us/support/legal/</Eula>
<PrivacyUri>https://azure.microsoft.com/en-us/support/legal/</PrivacyUri>
<HomepageUri>https://github.com/Azure/azure-linux-extensions</HomepageUri>
<IsJsonExtension>true</IsJsonExtension>
<SupportedOS>Linux</SupportedOS>
<CompanyName>Microsoft</CompanyName>
<!--%%REGIONS%%-->
</ExtensionImage>""" % (CommonVariables.extension_provider_namespace, CommonVariables.extension_type, CommonVariables.extension_version, CommonVariables.extension_label, CommonVariables.extension_description)

extension_xml_file = open('manifest.xml', 'w')
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
      author_email='opensource@microsoft.com',
      url='https://github.com/Azure/azure-linux-extensions',
      classifiers = ['Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
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
    args = ["dos2unix", src]
    devnull = open(os.devnull, 'w')
    child = subprocess.Popen(args, stdout=devnull, stderr=devnull)
    print('dos2unix %s ' % (src))
    child.wait()

def remove_utf8_bom(src):
    print('removing utf-8 bom from %s ' % (src))

    contents = None

    with open(src, "r+b") as fp:
        bincontents = fp.read()
        if bincontents[:len(codecs.BOM_UTF8)] == codecs.BOM_UTF8:
            contents = bincontents.decode('utf-8-sig')
        elif bincontents[:3] == '\xef\x00\x00':
            contents = bincontents[3:].decode('utf-8')
        else:
            contents = bincontents.decode('utf-8')

    with open(src, "wb") as fp:
        fp.write(contents.encode('utf-8'))

def zip(src, dst):
    zf = ZipFile("%s" % (dst), "w")
    abs_src = os.path.abspath(src)
    for dirname, subdirs, files in os.walk(src):
        for filename in files:
            absname = os.path.abspath(os.path.join(dirname, filename))
            dos2unix(absname)
            remove_utf8_bom(absname)
            arcname = absname[len(abs_src) + 1:]
            print('zipping %s as %s' % (os.path.join(dirname, filename), arcname))
            zf.write(absname, arcname)
    zf.close()

final_folder_path = target_zip_file_location + target_folder_name
# manually copy .json files since setup will only copy .py files by default
copy2(main_folder+'/SupportedOS.json', final_folder_path+'/'+main_folder )
copy2(main_folder+'/common_parameters.json', final_folder_path+'/'+main_folder )
zip(final_folder_path, target_zip_file_path)

