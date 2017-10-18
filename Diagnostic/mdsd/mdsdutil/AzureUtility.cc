// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "AzureUtility.hh"
#include "Utility.hh"
#include "Trace.hh"
#include <stdexcept>
#include <map>
#include <was/storage_account.h>
#include <was/table.h>
#include <was/blob.h>
#include <was/error_code_strings.h>

//////// Begin MdsdUtil namespace

namespace MdsdUtil {

void ValidateStorageCredentialForTable(const std::string& connStr)
{
    if (connStr.empty())
    {
        throw std::invalid_argument("Storage connection string cannot be empty");
    }

    // Method: Just calling cloud_table_client.list_tables() will
    // throw an exception with a proper message if the storage key
    // is not good (server auth failed) or if the storage account
    // name/type (e.g., Premium or Blob storage) is invalid (DNS
    // failure).

    azure::storage::cloud_storage_account::parse(connStr)
    .create_cloud_table_client()
    .list_tables();
}

void ValidateSAS(const std::string& sastoken, bool& isValidAccountSas)
{
    isValidAccountSas = false;

    std::map<std::string, std::string> qry;
    MdsdUtil::ParseQueryString(sastoken, qry);

    // Logic 1: If the sastoken doesn't contain 'ss' param,
    // we consider it a valid service SAS (not checking any further,
    // keeping the current behavior).
    auto ss = qry.find("ss");
    if (ss == qry.end()) {
        return;
    }

#define CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(param, entry, reason) \
    if (param.find(entry) == std::string::npos) {\
        throw MdsdInvalidSASException(reason);\
    }

    // Logic 2: If there's an 'ss' param, it should be an account SAS,
    // and needs the following entries in params:
    // 'ss' (SignedServices): must include 'b' (blob) and 't'
    // 'srt' (SignedResourceTypes): must include 'c' (container) and 'o' (object).
    //     May later need 's' (service) as well if we want to validate the SAS key by listing tables.
    // 'sp' (SignedPermissions): must include 'w' (write), 'u' (update), 'c' (create), 'a' (add), 'l' (list).
    //     'l' is still needed, because our ValidateStorageCredentialForTable() depends on list_tables().
    const char* ssReqMsg = "Account SAS must enable blob and table services (ss='bt' or better)";
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(ss->second, 'b', ssReqMsg);
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(ss->second, 't', ssReqMsg);

    const char* srtReqMsg = "Account SAS must enable container and object access (srt='co' or better)";
    auto srt = qry.find("srt");
    if (srt == qry.end()) {
        throw MdsdInvalidSASException(srtReqMsg);
    }
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(srt->second, 'c', srtReqMsg);
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(srt->second, 'o', srtReqMsg);

    const char* spReqMsg = "Account SAS must grant sp='acluw' permissions or better";
    auto sp = qry.find("sp");
    if (sp == qry.end()) {
        throw MdsdInvalidSASException(spReqMsg);
    }
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(sp->second, 'a', spReqMsg);
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(sp->second, 'c', spReqMsg);
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(sp->second, 'l', spReqMsg);
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(sp->second, 'u', spReqMsg);
    CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS(sp->second, 'w', spReqMsg);

#undef CHECK_MISSING_ENTRY_IN_ACCOUNT_SAS

    isValidAccountSas = true;
}


bool ContainerAlreadyExistsException(const azure::storage::storage_exception& e)
{
    const auto& r = e.result(); // handy reference
    return r.is_response_available()
            && (r.http_status_code() == web::http::status_codes::Conflict)
            && (r.extended_error().code() == azure::storage::protocol::error_code_container_already_exists);

}


void CreateContainer(const std::string & connectionString, const std::string & containerName)
{
    Trace trace(Trace::ConfigLoad, "MdsdUtil::CreateContainer");

    // Azure requires the container name to be all lower case
    std::string containerNameLC(MdsdUtil::to_lower(containerName));

    using namespace azure::storage;

    try {
        TRACEINFO(trace, "Parsing connection string \"" << connectionString << "\"");
        auto acct = cloud_storage_account::parse(connectionString);
        auto client = acct.create_cloud_blob_client();
        TRACEINFO(trace, "Get reference to container \"" << containerNameLC << "\"");
        auto container = client.get_container_reference(containerNameLC);

        // This is a synchronous call!
        TRACEINFO(trace, "Create container (noop if it already exists)");
        container.create(); // create_if_not_exists() needs read perm on account SAS,
                            // which is undesirable, so just use create() and swallow
                            // the ContainerAlreadyExists exception.
    }
    catch (const azure::storage::storage_exception& e) {
        if (MdsdUtil::ContainerAlreadyExistsException(e)) {
            TRACEINFO(trace, "Container already exists, ignoring the exception");
            return;
        }
        TRACEINFO(trace, "Exception: " << e.what());
        throw;
    }
    catch (const std::exception & e) {
        TRACEINFO(trace, "Exception: " << e.what());
        throw;
    }
}


};

//////////// MdsdUtil namespace ends
