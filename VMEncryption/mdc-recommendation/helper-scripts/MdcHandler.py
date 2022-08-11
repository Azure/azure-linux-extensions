from distutils.log import error
import json
import sys

import SupportedSkus
import ImdsHelper
import VerifyVMSupport
from DiskUtilHelper import DiskUtil

policy_reasons = {
    "code": "",
    "phrase": ""
    }

# List of OS images where ADE supports only VolumeType=Data
unsupported_images_ade_os_encryption = SupportedSkus.unsupported_images_ade_os_encryption

# Returns True if OS Disk encryption is supported by ADE for the VM OS distro
def os_volume_encryption_supported(imds_metadata):
    vm_os_offer = str(imds_metadata['compute']['storageProfile']['imageReference']['offer']).lower()
    vm_os_sku = str(imds_metadata['compute']['storageProfile']['imageReference']['sku']).lower()
    vm_image_tuple = tuple((vm_os_offer, vm_os_sku))

    if vm_image_tuple in unsupported_images_ade_os_encryption:
        return False

    return True

def check_hbe_encryption(imds_metadata):
    hbe_status = str(imds_metadata['compute']['securityProfile']['encryptionAtHost']).lower()
    if hbe_status is not None and ("true" in hbe_status):
        return True

    return False

def check_ade_encryption(imds_metadata):
    ade_status = False
    try:
        disk_util = DiskUtil()
        disk_status = disk_util.get_encryption_status()
        unencrypted_data_disks = disk_util.unencrypted_data_disks

        if disk_status['os'] == "Encrypted" and (disk_status['data'] == "Encrypted" or disk_status['data'] == "NotMounted"):
            ade_status = True
        elif disk_status['os'] == "NotEncrypted" and (disk_status['data'] == "Encrypted" or disk_status['data'] == "NotMounted"):
            is_os_volume_encryption_supported = os_volume_encryption_supported(imds_metadata)

            if is_os_volume_encryption_supported is True:
                ade_status = False
                if (disk_status['data'] == "Encrypted"):
                    policy_reasons['code'] = "OSDiskNotEncrypted"
                    policy_reasons['phrase'] = "VM is not fully encrypted with Azure Disk Encryption. OS disk is in an unencrypted state."
            else:
                ade_status = True
        elif disk_status['os'] == "Encrypted" and disk_status['data'] == "NotEncrypted":
                ade_status = False
                if len(unencrypted_data_disks) > 0:
                    reason_str = "VM is not fully encrypted with Azure Disk Encryption. The following data disks are not encrypted:"
                    for disk_item in unencrypted_data_disks:
                        reason_str += str(disk_item)
                    policy_reasons['code'] = "VMIsNotFullyEncrypted"
                    policy_reasons['phrase'] = reason_str

    except Exception as e:
        print("Exception occured in Python helper while detecting ADE status.")
        raise e

    if ade_status is True:
        policy_reasons['phrase'] += "VM is encryption compliant with Azure Disk Encryption."
        return True

    return False

def detect_encryption_status(imds_metadata):
    is_vm_hbe_encrypted = check_hbe_encryption(imds_metadata)
    is_vm_ade_encrypted = check_ade_encryption(imds_metadata)
    is_vm_compliant = False

    if (is_vm_hbe_encrypted is True):
        is_vm_compliant = True
        policy_reasons['code'] = "Compliant"
        policy_reasons['phrase'] = "VM is encryption compliant with Host Based Encryption."

    elif(is_vm_ade_encrypted is True):
        is_vm_compliant = True
        policy_reasons['code'] = "Compliant"
        policy_reasons['phrase'] = "VM is encryption compliant with Azure Disk Encryption."
    else:
        vm_support_dict = VerifyVMSupport.check_vm_supportability(imds_metadata)

        if vm_support_dict['is_vm_not_supported'] is True:
            is_vm_compliant = False
            policy_reasons['code'] = vm_support_dict['code']
            policy_reasons['phrase'] = vm_support_dict['phrase']
        else:
            is_vm_compliant = False
            if (policy_reasons['code'] == "" and policy_reasons['phrase'] == ""):
                policy_reasons['code'] = "MissingADEandHBE"
                policy_reasons['phrase'] = "VM is not encrypted. VM should be encrypted with Host Based Encryption or Azure Disk Encryption"

    return is_vm_compliant

def output_results_to_json(json_output_file_path, is_vm_compliant, errorMsg):
    policy_reasons_output = []
    policy_result = {"isCompliant" : is_vm_compliant}

    if errorMsg is not None:
        policy_reasons_output += [errorMsg]
    else:
        policy_reasons_string = policy_reasons["code"] + "?" + policy_reasons["phrase"]
        policy_reasons_output += [policy_reasons_string]

    gc_result = {
        "result": policy_result,
        "reasons": policy_reasons_output
    }

    json_output = json.dumps(gc_result, indent=4)

    with open(json_output_file_path, 'w') as f:
        f.write(json_output)
        print("Compliance output has been written to JSON file.")
        f.close()

def main():
    try:
        exception_found = False

        json_output_file_path = sys.argv[2]
        imds_metadata = ImdsHelper.get_imds_metadata()
        if imds_metadata is None:
            msg = "Python helper failed in fetching IMDS metadata"
            raise Exception(msg)

        is_vm_compliant = detect_encryption_status(imds_metadata)

    except Exception as e:
        exception_found = True
        exception_message = str(e)

    finally:
        if exception_found is True:
            errorMsg = "Exception occured in Python helper script. Error:" + exception_message
        else:
            errorMsg = None

        output_results_to_json(json_output_file_path, is_vm_compliant, errorMsg)

if __name__ == "__main__":
    main()
