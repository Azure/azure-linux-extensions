/* @migen@ */
#include <MI.h>
#include "LinuxEncryptionCompliance.h"

// C++ libraries
#include <string>
#include <memory>
#include <fstream>
#include <iostream>

#include <libgen.h>         // dirname
#include <unistd.h>         // readlink
#include <linux/limits.h>   // PATH_MAX

#include "nlohmann/json.hpp"

#define DSC_PATH_SEPARATOR "/"
#define SHIM_CALLER_NAME "extension_shim.sh"
#define PYTHON_DRIVER_SCRIPT_NAME "MdcHandler.py"
#define JSON_OUTPUT_FILE_NAME "mdc_compliance_output.json"

void MI_CALL LinuxEncryptionCompliance_Load(
    _Outptr_result_maybenull_ LinuxEncryptionCompliance_Self** self,
    _In_opt_ MI_Module_Self* selfModule,
    _In_ MI_Context* context)
{
    MI_UNREFERENCED_PARAMETER(selfModule);

    *self = NULL;
    MI_Context_PostResult(context, MI_RESULT_OK);
}

void MI_CALL LinuxEncryptionCompliance_Unload(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context)
{
    MI_UNREFERENCED_PARAMETER(self);

    MI_Context_PostResult(context, MI_RESULT_OK);
}

void MI_CALL LinuxEncryptionCompliance_EnumerateInstances(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_ const MI_PropertySet* propertySet,
    _In_ MI_Boolean keysOnly,
    _In_opt_ const MI_Filter* filter)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(propertySet);
    MI_UNREFERENCED_PARAMETER(keysOnly);
    MI_UNREFERENCED_PARAMETER(filter);

    MI_Context_PostResult(context, MI_RESULT_NOT_SUPPORTED);
}

void MI_CALL LinuxEncryptionCompliance_GetInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const MI_PropertySet* propertySet)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(instanceName);
    MI_UNREFERENCED_PARAMETER(propertySet);

    MI_Context_PostResult(context, MI_RESULT_NOT_SUPPORTED);
}

void MI_CALL LinuxEncryptionCompliance_CreateInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* newInstance)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(newInstance);

    MI_Context_PostResult(context, MI_RESULT_NOT_SUPPORTED);
}

void MI_CALL LinuxEncryptionCompliance_ModifyInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* modifiedInstance,
    _In_opt_ const MI_PropertySet* propertySet)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(modifiedInstance);
    MI_UNREFERENCED_PARAMETER(propertySet);

    MI_Context_PostResult(context, MI_RESULT_NOT_SUPPORTED);
}

void MI_CALL LinuxEncryptionCompliance_DeleteInstance(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_ const LinuxEncryptionCompliance* instanceName)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(instanceName);

    MI_Context_PostResult(context, MI_RESULT_NOT_SUPPORTED);
}

std::string join_path(const std::string& p1, const std::string& p2)
{
    char sep = '/';
    std::string tmp = p1;

#ifdef _WIN32
    sep = '\\';
#endif

    if (p1[p1.length() - 1] != sep) {
        tmp += sep;
        return tmp + p2;
    } else {
        return p1 + p2;
    }
}

std::string parent_path(std::string path)
{
    return path.substr(0, path.find_last_of("/\\"));
}

void *safe_malloc(size_t size)
{
    void *return_pointer = malloc(size);
    if (return_pointer == NULL)
    {
        throw std::runtime_error("safe_malloc of " + std::to_string((unsigned)size) + " bytes failed.");
    }
    return return_pointer;
}

// Retrieves the path of the DSC folder by retrieving the path to the current executable.
std::string get_dsc_folder_path(MI_Context *context)
{
    // Get dsc folder path from DSC engine.
    if(context) {
        MI_Result result = MI_RESULT_OK;
        MI_Type type;
        MI_Value value;
        result = MI_Context_GetCustomOption(context, MI_T("GuestConfigurationPath"), &type, &value);
        if(result == MI_RESULT_OK) {
            std::string dsc_folder_path = value.string;
            return dsc_folder_path;
        }
    }

    // Compute dsc folder path from current process path.
    char result[PATH_MAX];
    std::string current_exe_path;
    ssize_t count = readlink("/proc/self/exe", result, PATH_MAX);
    if (count != -1) {
        current_exe_path = dirname(result);
    }
    else
    {
        throw std::runtime_error("Failed to find GuestConfigurationPath.");
    }
    
    return current_exe_path;
}

std::string config_folder_path(MI_Context *context)
{
    // Get the configuration folder path from DSC engine.
    // Sample path : '/var/lib/GuestConfig/Configuration/PasswordPolicy_msid232/'
    if(context) {
        MI_Result result = MI_RESULT_OK;
        MI_Type type;
        MI_Value value;
        result = MI_Context_GetCustomOption(context, MI_T("AssignmentPath"), &type, &value);
        if(result == MI_RESULT_OK) {
            std::string dsc_folder_path = value.string;
            dsc_folder_path = parent_path(dsc_folder_path);
            dsc_folder_path = parent_path(dsc_folder_path);
            return dsc_folder_path;
        }
    }

    // Compute dsc folder path from current process path.
    std::string dsc_folder_path = get_dsc_folder_path(context);
    dsc_folder_path = parent_path(dsc_folder_path);
    std::string config_folder_path = join_path(dsc_folder_path, "Configuration");
    return config_folder_path;
}

// Retrieves the path to the python helper scripts folder for encryption detection.
std::string get_helper_scripts_folder_path(MI_Context *context, std::string policy_name)
{
    //std::string helper_scripts_folder_path = "";
    if(context) {
        MI_Result result = MI_RESULT_OK;
        MI_Type type;
        MI_Value value;
        result = MI_Context_GetCustomOption(context, MI_T("AssignmentPath"), &type, &value);
        if(result == MI_RESULT_OK) {
            std::string policy_config_folder_path = value.string;
            std::string policy_modules_folder_path = join_path(policy_config_folder_path, "Modules");
            std::string helper_scripts_folder_path = join_path(policy_modules_folder_path, "helper");
            MI_Context_WriteVerbose(context, ("policy_config_folder_path: " + policy_config_folder_path).c_str());
            return helper_scripts_folder_path;
        }
    }

    std::string gcagent_config_folder_path = config_folder_path(context);
    MI_Context_WriteVerbose(context, ("gcagent-config-folder-path: " + gcagent_config_folder_path).c_str());
    std::string policy_config_folder_path = join_path(gcagent_config_folder_path, policy_name);
    std::string policy_modules_folder_path = join_path(policy_config_folder_path, "Modules");
    std::string helper_scripts_folder_path = join_path(policy_modules_folder_path, "helper");
    return helper_scripts_folder_path;
}

// Retrieves the reasons of any audit policy failures and constructs the Reasons property object.
MI_Result get_policy_reasons(MI_Context *context, std::vector<std::string> reason_phrases, MI_Value &results_value)
{
    MI_Result mi_result = MI_RESULT_OK;

    MI_Value temp_mi_value;

    int reasons_size = reason_phrases.size() * sizeof(MI_Instance*);
    MI_Instance **reasons = (MI_Instance**) safe_malloc(reasons_size);

    try
    {
        for (unsigned int reason_index = 0; reason_index < reason_phrases.size(); reason_index++)
        {
            // Create the reason MI instance
            mi_result = MI_Context_NewInstance(context, &Audit_Reason_rtti, &reasons[reason_index]);
            if (mi_result != MI_RESULT_OK)
            {
                MI_Context_WriteVerbose(context, "Failed to create a reason instance for the audit resource.");
                throw std::runtime_error("Failed to create a reason instance for the resource.");
            }

            size_t loc = reason_phrases[reason_index].find("?");
            std::string code = reason_phrases[reason_index].substr(0, loc);
            std::string phrase = reason_phrases[reason_index].substr(loc + 1);
            temp_mi_value.string = (char *)code.c_str();

            mi_result = MI_Instance_SetElement(reasons[reason_index], MI_T("Code"), &temp_mi_value, MI_STRING, 0 );
            if (mi_result != MI_RESULT_OK)
            {
                MI_Context_WriteVerbose(context, "Failed to populate the 'Code' property of a reason instance.");
                throw std::runtime_error("Failed to populate the 'Code' property of a reason instance.");
            }

            temp_mi_value.string = (char *)phrase.c_str();
            mi_result = MI_Instance_SetElement(reasons[reason_index], MI_T("Phrase"), &temp_mi_value, MI_STRING, 0 ); 
            if (mi_result != MI_RESULT_OK)
            {
                MI_Context_WriteVerbose(context, "Failed to populate the 'Phrase' property of a reason instance.");
                throw std::runtime_error("Failed to populate the 'Phrase' property of a reason instance.");
            }
        }
        results_value.instancea.size = reason_phrases.size();
        results_value.instancea.data = reasons;
    }
    catch (std::runtime_error &runtime_exc)
    {
        MI_Context_WriteVerbose(context, "Error: get_policy_reaons() catch.");
        MI_Context_PostError(context, mi_result, MI_RESULT_TYPE_MI, runtime_exc.what());
    }

    return mi_result;
}

// Runs the python helper script to detect encryption compliance
void run_python_helper_script(MI_Context *context, std::string policy_name)
{
    try
    {
        std::array<char, 20000> buffer;
        std::string process_output;

        // Retrieve full path of the helper scripts
        std::string helper_scripts_folder_path = get_helper_scripts_folder_path(context, policy_name);
        std::string shim_caller_path = helper_scripts_folder_path + DSC_PATH_SEPARATOR + SHIM_CALLER_NAME;
        std::string python_driver_path = helper_scripts_folder_path + DSC_PATH_SEPARATOR + PYTHON_DRIVER_SCRIPT_NAME;
        std::string json_output_file_path = helper_scripts_folder_path + DSC_PATH_SEPARATOR + JSON_OUTPUT_FILE_NAME;        
        std::string run_encryption_audit = "bash " + shim_caller_path + " -c " + "\"" + python_driver_path + " --install " + json_output_file_path + "\"" + " 2>&1";
        std::cout << "Command to execute: " << run_encryption_audit << std::endl;

        auto pyhelper_process_stream = popen(run_encryption_audit.c_str(), "r");

        if (NULL == pyhelper_process_stream)
        {
            MI_Context_WriteVerbose(context, "popen() for Python helper script failed.");
            throw std::runtime_error("popen() for Python helper script failed.");
        }
        MI_Context_WriteVerbose(context, "Python helper script finished execution.");

        try
        {
            while (!feof(pyhelper_process_stream))
            {
                if (fgets(buffer.data(), 20000, pyhelper_process_stream) != nullptr)
                    process_output += buffer.data();
            }
        }
        catch (...)
        {
            pclose(pyhelper_process_stream);
            MI_Context_WriteVerbose(context, "Error occured while processing file stream output for python helper.");
            throw std::runtime_error("Error occured while processing file stream output for python helper.");
        }
        
        pclose(pyhelper_process_stream);
        MI_Context_WriteVerbose(context, ("PYTHON HELPER OUTPUT LOG:" + process_output).c_str());       
        std::cout << "Python helper output " << process_output << std::endl;
    }
    catch (std::runtime_error &runtime_exc)
    {
        MI_Context_WriteVerbose(context, "Error: run_audit_policy_script() catch. Executing Python helper script for encryption detection failed.");
        throw std::runtime_error("Executing Python helper script for encryption detection failed.");
    }
}

// Parse the JSON output from output file to get reasons and compliance status
void process_json_output(MI_Context *context, std::string policy_name, bool &compliance_status, std::vector<std::string> &reason_phrases)
{
    try
    {
        std::string helper_scripts_folder_path = get_helper_scripts_folder_path(context, policy_name);
        std::string json_output_file_path = join_path(helper_scripts_folder_path, JSON_OUTPUT_FILE_NAME);

        std::cout << "Opening json file with parse " << std::cout<<json_output_file_path<< std::endl;

        std::ifstream ifs(json_output_file_path);
        nlohmann::json root = nlohmann::json::parse(ifs);
        MI_Context_WriteVerbose(context, "Parsing JSON output file for compliance result..");
        compliance_status = root["result"]["isCompliant"];
        MI_Context_WriteVerbose(context, "Fetched result from JSON file.");

        MI_Context_WriteVerbose(context, "Parsing JSON output file for reasons..");
        for (auto &reason : root["reasons"])
        {
            reason_phrases.push_back(reason);
        }
        MI_Context_WriteVerbose(context, "Fetched reasons from JSON file.");
    }
    catch (std::runtime_error &runtime_exc)
    {
        MI_Context_WriteVerbose(context, "Error: run_audit_policy_script() catch");
        throw std::runtime_error("Executing Python helper script for encryption detection failed.");
    }
}

void MI_CALL LinuxEncryptionCompliance_Invoke_GetTargetResource(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_z_ const MI_Char* methodName,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const LinuxEncryptionCompliance_GetTargetResource* in)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(methodName);
    MI_UNREFERENCED_PARAMETER(instanceName);
    MI_UNREFERENCED_PARAMETER(in);

    MI_Result mi_result = MI_RESULT_OK;
    MI_Instance *resource_result_object = NULL;
    std::string policy_name = "";

    MI_Value string_mi_value;
    MI_Value result_mi_value;
    MI_Value reasons_mi_value;
    MI_Value resource_mi_value;

    memset(&string_mi_value, 0, sizeof(MI_Value));
    memset(&result_mi_value, 0, sizeof(MI_Value));
    memset(&reasons_mi_value, 0, sizeof(MI_Value));
    memset(&resource_mi_value, 0, sizeof(MI_Value));

    MI_Context_WriteVerbose(context, MI_T("Starting Get on the LinuxEncryptionCompliance resource..."));
    LinuxEncryptionCompliance_GetTargetResource get_result_object;
    try
    {
        // Validate that a non-null input resource with a non-null value was provided for this function
        if (in == NULL || in->InputResource.exists == MI_FALSE || in->InputResource.value == NULL)
        {
            throw std::runtime_error("No input provided to the LinuxEncryptionCompliance resource.");
        }

        // key is exists and value is not null
        if (in->InputResource.value->PolicyName.exists == MI_FALSE &&  in->InputResource.value->PolicyName.value != NULL)
        {
            throw std::runtime_error("The LinuxEncryptionCompliance resource is missing a value for the 'PolicyName' property.");
        }
        policy_name = (char *)in->InputResource.value->PolicyName.value;

        // Construct the GetTargetResource instance and return value
        mi_result = LinuxEncryptionCompliance_GetTargetResource_Construct(&get_result_object, context);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to construct the MI instance for the LinuxEncryptionCompliance GetTargetResource result.");
        }

        mi_result = LinuxEncryptionCompliance_GetTargetResource_Set_MIReturn(&get_result_object, 0);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to set the MI instance return value for the LinuxEncryptionCompliance GetTargetResource result.");
        }

        // Create the output resource instance
        mi_result = MI_Context_NewInstance(context, &LinuxEncryptionCompliance_rtti, &resource_result_object);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to create a new MI instance for the LinuxEncryptionCompliance output resource instance.");
        }

        // Fill in the PolicyName property of the output resource instance
        string_mi_value.string = (MI_Char*)in->InputResource.value->PolicyName.value;
        mi_result = MI_Instance_SetElement(resource_result_object, MI_T("PolicyName"), &string_mi_value, MI_STRING, 0);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to populate the 'PolicyName' property of the output resource instance.");
        }                

        // Encryption detection logic begins here
        std::vector<std::string> reason_phrases;
        bool compliance_status;

        run_python_helper_script(context, policy_name);
        process_json_output(context, policy_name, compliance_status, reason_phrases);

        // Fill reasons field        
        mi_result = get_policy_reasons(context, reason_phrases, reasons_mi_value);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to retrieve the results of the policy.");
        }

        mi_result = MI_Instance_SetElement(resource_result_object, MI_T("Reasons"), &reasons_mi_value,  MI_INSTANCEA, 0);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to populate the 'Reasons' property of the output resource instance.");
        }

        // Set the temp MI value to the output resource instance
        resource_mi_value.instance = resource_result_object;

        // Set the created output resource instance as the output resource in the GetTargetResource instance
        mi_result = MI_Instance_SetElement(&get_result_object.__instance, MI_T("OutputResource"), &resource_mi_value, MI_INSTANCE, 0);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to populate the 'OutputResource' property of the GetTargetResource instance.");
        }

        // Post the GetTargetResource instance
        mi_result = LinuxEncryptionCompliance_GetTargetResource_Post(&get_result_object, context);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to post the GetTargetResource instance.");
        }        
    }
    catch (std::runtime_error &runtime_exc)
    {
        mi_result = MI_RESULT_FAILED;
        MI_Context_PostError(context, mi_result, MI_RESULT_TYPE_MI, runtime_exc.what());
    }

    // Clean up the Result MI value instance if needed
    if (result_mi_value.instance != NULL)	
    {
        if (MI_Instance_Delete(result_mi_value.instance) != MI_RESULT_OK)
        {
            MI_Context_WriteVerbose(context, MI_T("Failed to delete the Result MI value instance."));
        }
    }

    // Clean up the Reasons MI value instance if needed
    if (reasons_mi_value.instancea.data != NULL)	
    {	
        for (unsigned int reason_index = 0; reason_index < reasons_mi_value.instancea.size; reason_index++)
        {
            if (MI_Instance_Delete(reasons_mi_value.instancea.data[reason_index]) != MI_RESULT_OK)
            {
                MI_Context_WriteVerbose(context, MI_T("Failed to delete an Reason MI value instance."));
            }
        }
        free(reasons_mi_value.instancea.data);
        reasons_mi_value.instancea.data = NULL;
        reasons_mi_value.instancea.size = 0;
    }

    // Clean up the output resource instance
    if (resource_result_object != NULL)
    {
        if (MI_Instance_Delete(resource_result_object) != MI_RESULT_OK)
        {
            MI_Context_WriteVerbose(context, MI_T("Failed to delete the resource MI instance."));
        }
    }

    // Clean up the GetTargetResource instance
    if (LinuxEncryptionCompliance_GetTargetResource_Destruct(&get_result_object) != MI_RESULT_OK)
    {
        MI_Context_WriteVerbose(context, MI_T("Failed to delete the GetTargetResource MI instance."));
    }
    
    // Post MI result back to MI to finish
    MI_Context_WriteVerbose(context, MI_T("Completed Get on the LinuxEncryptionCompliance resource."));
    MI_Context_PostResult(context, mi_result);
}

void MI_CALL LinuxEncryptionCompliance_Invoke_TestTargetResource(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_z_ const MI_Char* methodName,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const LinuxEncryptionCompliance_TestTargetResource* in)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(methodName);
    MI_UNREFERENCED_PARAMETER(instanceName);
    MI_UNREFERENCED_PARAMETER(in);

    LinuxEncryptionCompliance_TestTargetResource test_result_object;

    MI_Result mi_result = MI_RESULT_OK;
    MI_Boolean is_compliant = MI_FALSE;
    
    MI_Value result_mi_value;
    memset(&result_mi_value, 0, sizeof(MI_Value));

    std::string policy_name = "";

    MI_Context_WriteVerbose(context, MI_T("Starting Test on the LinuxEncryptionCompliance resource..."));

    try
    {
        // Validate that a non-null input resource with a non-null value was provided for this function
        if (in == NULL || in->InputResource.exists == MI_FALSE || in->InputResource.value == NULL)
        {
            throw std::runtime_error("No input provided to the LinuxEncryptionCompliance resource.");
        }

        // key is exists and value is not null
        if (in->InputResource.value->PolicyName.exists == MI_FALSE &&  in->InputResource.value->PolicyName.value != NULL)
        {
            throw std::runtime_error("The LinuxEncryptionCompliance resource is missing a value for the 'PolicyName' property.");
        }
        policy_name = (char *)in->InputResource.value->PolicyName.value;

        // Encryption detection logic begins here
        std::vector<std::string> reason_phrases;
        bool compliance_status;

        run_python_helper_script(context, policy_name);
        process_json_output(context, policy_name, compliance_status, reason_phrases);

        if (compliance_status == 1)
        {
            is_compliant = MI_TRUE;
        }

        // Construct the TestTargetResource instance and return value
        mi_result = LinuxEncryptionCompliance_TestTargetResource_Construct(&test_result_object, context);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to construct the MI instance for the TestTargetResource result.");
        }

        mi_result = LinuxEncryptionCompliance_TestTargetResource_Set_MIReturn(&test_result_object, 0);
        if (mi_result != MI_RESULT_OK)
        {
            throw std::runtime_error("Failed to set the MI instance return value for the TestTargetResource result.");
        }

        // Return the status of the specified policy
        LinuxEncryptionCompliance_TestTargetResource_Set_Result(&test_result_object, is_compliant);
        MI_Context_PostInstance(context, &(test_result_object.__instance));
    }
    catch (std::runtime_error &runtime_exc)
    {
        mi_result = MI_RESULT_OK;
        MI_Context_PostError(context, mi_result, MI_RESULT_TYPE_MI, runtime_exc.what());
    }

    // Clean up the Result MI value instance if needed
    if (result_mi_value.instance != NULL)	
    {
        if (MI_Instance_Delete(result_mi_value.instance) != MI_RESULT_OK)
        {
            MI_Context_WriteVerbose(context, MI_T("Failed to delete the Result MI value instance."));
        }
    }

    // Clean up the TestTargetResource instance
    if (LinuxEncryptionCompliance_TestTargetResource_Destruct(&test_result_object) != MI_RESULT_OK)
    {
        MI_Context_WriteVerbose(context, MI_T("Failed to delete the TestTargetResource MI instance."));
    }

    // Post MI result back to MI to finish    
    MI_Context_WriteVerbose(context, MI_T("Completed Test on the LinuxEncryptionCompliance resource."));
    MI_Context_PostResult(context, mi_result);
}

void MI_CALL LinuxEncryptionCompliance_Invoke_SetTargetResource(
    _In_opt_ LinuxEncryptionCompliance_Self* self,
    _In_ MI_Context* context,
    _In_opt_z_ const MI_Char* nameSpace,
    _In_opt_z_ const MI_Char* className,
    _In_opt_z_ const MI_Char* methodName,
    _In_ const LinuxEncryptionCompliance* instanceName,
    _In_opt_ const LinuxEncryptionCompliance_SetTargetResource* in)
{
    MI_UNREFERENCED_PARAMETER(self);
    MI_UNREFERENCED_PARAMETER(nameSpace);
    MI_UNREFERENCED_PARAMETER(className);
    MI_UNREFERENCED_PARAMETER(methodName);
    MI_UNREFERENCED_PARAMETER(instanceName);
    MI_UNREFERENCED_PARAMETER(in);

    MI_Context_PostResult(context, MI_RESULT_NOT_SUPPORTED);
}

