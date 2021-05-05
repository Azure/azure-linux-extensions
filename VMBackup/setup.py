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
import shutil
import tempfile
import json
import sys
import subprocess
import shutil
import time
from subprocess import call
from zipfile import ZipFile
from main.common import CommonVariables

packages_array = []
main_folder = 'main'
main_entry = main_folder + '/handle.sh'
binary_entry = main_folder + '/safefreeze'
packages_array.append(main_folder)

plugin_folder = main_folder + '/tempPlugin'
plugin_conf =  main_folder + '/VMSnapshotPluginHost.conf'


patch_folder = main_folder + '/patch'
packages_array.append(patch_folder)

workloadpatch_folder = main_folder + '/workloadPatch'
workloadutils_folder = main_folder + '/workloadPatch/WorkloadUtils'
workloadscripts_folder = main_folder + '/workloadPatch/DefaultScripts'
workload_customscripts_folder = main_folder + '/workloadPatch/CustomScripts'
sqlfilelists=os.listdir(workloadscripts_folder)
custom_sqlfilelists=os.listdir(workload_customscripts_folder)
packages_array.append(workloadpatch_folder)

manifest = "manifest.xml"

"""
copy the dependency to the local
"""

"""
copy the utils lib to local
"""
target_utils_path = main_folder + '/' + CommonVariables.utils_path_name
#if os.path.isdir(target_utils_path):
#    shutil.rmtree(target_utils_path)
#print('copying')
#shutil.copytree ('../' + CommonVariables.utils_path_name, target_utils_path)
#print('copying end')
packages_array.append(target_utils_path)


"""
generate the HandlerManifest.json file.
"""
manifest_obj = [{
  "name": CommonVariables.extension_name,
  "version": CommonVariables.extension_version,
  "handlerManifest": {
    "installCommand": main_entry + " install",
    "uninstallCommand": main_entry + " uninstall",
    "updateCommand": main_entry + " update",
    "enableCommand": main_entry + " enable",
    "disableCommand": main_entry + " disable",
    "rebootAfterInstall": False,
    "reportHeartbeat": False
  }
}]

manifest_str = json.dumps(manifest_obj, sort_keys = True, indent = 4)
manifest_file = open("HandlerManifest.json", "w") 
manifest_file.write(manifest_str)
manifest_file.close()

"""
generate the safe freeze binary
"""
cur_dir = os.getcwd()
os.chdir("./main/safefreeze")
chil = subprocess.Popen(["make"], stdout=subprocess.PIPE)
process_wait_time = 5
while(process_wait_time >0 and chil.poll() is None):
    time.sleep(1)
    process_wait_time -= 1

os.chdir(cur_dir)


"""
setup script, to package the files up
"""
setup(name = CommonVariables.extension_name,
      version = CommonVariables.extension_zip_version,
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
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: SQL',
        'Programming Language :: PL/SQL'],
      packages = packages_array
      )

"""
unzip the package files and re-package it.
"""



target_zip_file_location = './dist/'
target_folder_name = CommonVariables.extension_name  + '-' + CommonVariables.extension_zip_version
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

def copybinary(src, dst):
    shutil.copytree(src, dst)

def copy(src, dst):
    shutil.copy2(src, dst)

final_folder_path = target_zip_file_location + target_folder_name
final_binary_path= final_folder_path + '/main/safefreeze'
final_plugin_path = final_folder_path + '/main/tempPlugin'
final_workloadscripts_path = final_folder_path + '/main/workloadPatch/DefaultScripts'
final_workload_customscripts_path = final_folder_path + '/main/workloadPatch/CustomScripts'
final_workloadutils_path = final_folder_path + '/main/workloadPatch/WorkloadUtils'
copybinary(workloadscripts_folder, final_workloadscripts_path) 
copybinary(workload_customscripts_folder, final_workload_customscripts_path)
copybinary(workloadutils_folder, final_workloadutils_path)
final_plugin_conf_path = final_folder_path + '/main'
copybinary(binary_entry, final_binary_path)
copybinary(plugin_folder, final_plugin_path)
copy(plugin_conf, final_plugin_conf_path)
copy(manifest,final_folder_path)
copy(main_entry,final_plugin_conf_path)
zip(final_folder_path, target_zip_file_path)

