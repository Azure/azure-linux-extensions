import SupportedSkus

# List of VM Sizes unsupported by HBE
unsupported_vm_sku_hbe_encryption = SupportedSkus.unsupported_vm_sku_hbe_encryption

# List of OS distros supported by ADE Linux encryption
supported_ade_image_list = SupportedSkus.supported_ade_image_list

# List of VM Sizes unsupported by ADE and HBE (Basic and A series VMs)
unsupported_vm_size_list = ["basic", "standard_a0", "standard_a1"]

# JSON property value for Confidential VM security type in IMDS metadata
cvm_metadata_value = "confidentialvm"

# Prefix for VM using Classic Compute provider, Kubernetes or Databricks
classic_compute_prefix = "classiccompute"
microsoft_databrick_image_publisher = "azuredatabricks"
microsoft_aks_image_publisher = "microsoft-aks"
aks_prefix = "aks"

def verify_vm_os_sku_completeness(imds_metadata):
    vm_image_publisher = imds_metadata['compute']['storageProfile']['imageReference']['publisher']
    vm_image_sku = imds_metadata['compute']['storageProfile']['imageReference']['sku']
    vm_os_offer = imds_metadata['compute']['storageProfile']['imageReference']['offer']

    if vm_image_publisher is None or vm_image_sku is None or vm_os_offer is None:
        return False

    return True

def is_confidential_vm(imds_metadata):
    cvm_status = imds_metadata['compute']['securityProfile']['securityType']
    is_confidential_vm = False
    
    if cvm_status is not None:
        cvm_status = str(cvm_status).lower()
        if cvm_metadata_value in cvm_status:
            is_confidential_vm = True
        
    return is_confidential_vm

def is_basic_vm(imds_metadata):
    vm_size = imds_metadata['compute']['vmSize']
    is_vm_size_unsupported = False
    
    if vm_size is not None:
        vm_size = str(imds_metadata['compute']['vmSize']).lower()
        is_vm_size_unsupported = any(vm_sku in vm_size for vm_sku in unsupported_vm_size_list)
        
    return is_vm_size_unsupported

def is_classic_vm(imds_metadata):
    vm_type = imds_metadata['compute']['provider']
    
    is_vm_type_unsupported = False
    
    if vm_type is not None:
        vm_type = str(imds_metadata['compute']['provider']).lower()
        if classic_compute_prefix in vm_type:
            is_vm_type_unsupported = True
            
    return is_vm_type_unsupported    

def is_kubernetes_vm(imds_metadata):
    vm_image_publisher = imds_metadata['compute']['storageProfile']['imageReference']['publisher']
    vm_image_sku = imds_metadata['compute']['storageProfile']['imageReference']['sku']
    is_kubernetes_vm = False

    if (microsoft_aks_image_publisher in vm_image_publisher) or (vm_image_sku.startswith(aks_prefix)):
            is_kubernetes_vm = True
    elif (microsoft_databrick_image_publisher in vm_image_publisher):
        is_kubernetes_vm = True

    return is_kubernetes_vm

def is_databricks_vm(imds_metadata):
    vm_image_publisher = imds_metadata['compute']['storageProfile']['imageReference']['publisher']
    vm_image_sku = imds_metadata['compute']['storageProfile']['imageReference']['sku']    
    is_databricks_vm = False 

    if (microsoft_aks_image_publisher in vm_image_publisher) or (vm_image_sku.startswith(aks_prefix)):
        is_databricks_vm = True
        reasons_phrase_str += "Databricks VM is not supported for ADE or HBE encryption."
    elif (microsoft_databrick_image_publisher in vm_image_publisher):
        is_databricks_vm = True

    return is_databricks_vm

def is_vm_using_ultra_disks(imds_metadata):
    vm_data_disks = imds_metadata['compute']['storageProfile']['dataDisks']
    is_vm_using_ultra_disk = False

    if len(vm_data_disks) > 0:    
        for disk in vm_data_disks:
            ultra_disk_flag = disk['isUltraDisk']
            if (ultra_disk_flag is not None) and ("true" in str(ultra_disk_flag).lower()):
                is_vm_using_ultra_disk = True
                break
  
    return is_vm_using_ultra_disk

# The below method covers a small intersection of scenarios where the OS distro is unsupported by ADE and VM size is unsupported by HBE.
def is_os_vmsize_unsupported(imds_metadata):
    unsupported_os_and_vm_size = False 
    vm_os_offer = imds_metadata['compute']['storageProfile']['imageReference']['offer']
    vm_os_sku = imds_metadata['compute']['storageProfile']['imageReference']['sku']
    vm_image_tuple = tuple((vm_os_offer, vm_os_sku))
    vm_size = imds_metadata['compute']['vmSize']

    if vm_size is not None:
        if (vm_image_tuple not in supported_ade_image_list) and (vm_size in unsupported_vm_sku_hbe_encryption):
            unsupported_os_and_vm_size = True
        
    return unsupported_os_and_vm_size
    
def check_vm_supportability(imds_metadata):
    #check if VM is supported for ADE or HBE encryption
    is_vm_not_supported = False
    reasons_code = ""
    reasons_phrase_str = ""
    vm_support_dict = {}
    
    if is_basic_vm(imds_metadata):
        is_vm_not_supported = True
        reasons_code = "BasicSizedVirtualMachine"
        reasons_phrase_str += "VM size is not supported by Azure Disk Encryption and EncryptionAtHost."

    if is_classic_vm(imds_metadata):
        is_vm_not_supported = True
        reasons_code = "ClassicVirtualMachine"
        reasons_phrase_str += "Classic VM is not supported by Azure Disk Encryption and EncryptionAtHost."

    if is_vm_using_ultra_disks(imds_metadata):
        is_vm_not_supported = True
        reasons_code = "UltraDisksVirtualMachine"
        reasons_phrase_str += "VM is using ultra disks which is currently not supported by Azure Disk Encryption and EncryptionAtHost."

    if verify_vm_os_sku_completeness(imds_metadata) is False:
        vm_support_dict['is_vm_not_supported'] = True
        vm_support_dict['code'] = "UnknownOsVirtualMachine"
        vm_support_dict['phrase'] = "VM OS details are missing in IMDS metadata for verification"
        return vm_support_dict

    if is_kubernetes_vm(imds_metadata):
        is_vm_not_supported = True
        reasons_code = "KubernetesVirtualMachine"
        reasons_phrase_str += "Azure Kubernetes VM is not supported by Azure Disk Encryption and EncryptionAtHost."

    if is_databricks_vm(imds_metadata):
        is_vm_not_supported = True
        reasons_code = "DatabrickVirtualMachine"
        reasons_phrase_str += "Azure Databricks VM is not supported by Azure Disk Encryption and EncryptionAtHost."

    if is_os_vmsize_unsupported(imds_metadata):
        is_vm_not_supported = True
        reasons_code = "UnsupportedOsVirtualMachine"
        reasons_phrase_str += "VM OS Image Sku is not supported by Azure Disk Encryption. VM Size Sku is not supported by EncryptionAtHost."

    vm_support_dict['is_vm_not_supported'] = is_vm_not_supported
    vm_support_dict['code'] = reasons_code
    vm_support_dict['phrase'] = reasons_phrase_str
        
    return vm_support_dict
