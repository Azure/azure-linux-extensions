// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XTableHelper.hh"
#include "XTableConst.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "Utility.hh"

using namespace azure::storage;
using std::string;

XTableHelper*
XTableHelper::GetInstance()
{
    static XTableHelper* s_instance = new XTableHelper();
    return s_instance;
}

XTableHelper::XTableHelper()
{
}

// Delete all the cloud_table objects stored in the cache map.
XTableHelper::~XTableHelper()
{
    Trace trace(Trace::XTable, "XTableHelper destructor");

    try
    {
        cloudTableMap.clear();
    }
    catch(const std::exception& e)
    {
        LogError("Error: ~XTableHelper(): unexpected std::exception: " + string(e.what()));
    }
    catch(...)
    {
    }
}

/*
  Each new table object is saved in the hash table. Because the hash table will
  be shared by multiple threads, using mutex lock for table operations.
  
  The tablename is the actual table name, not a URI. Ie the connStr specifies a SAS, then Azure requires
  the tablename to match the tn= component in the SAS; otherwise, either fetching the table reference will
  fail (here) or using it will fail (probably by the caller of this function).
 */
std::shared_ptr<azure::storage::cloud_table>
XTableHelper::CreateTable(const string& tablename, const string& connStr)
{    
    Trace trace(Trace::XTable, "XTableHelper::CreateTable");
    std::shared_ptr<azure::storage::cloud_table> tableObj;

    try {
        trace.NOTE("tablename='" + tablename + "'; connection string='" + connStr + "'.");
        if (MdsdUtil::NotValidName(tablename)) {
            LogError("Error: invalid table name: '" + tablename + "'; connection string='" + connStr + "'.");
            return nullptr;
        }
        if (MdsdUtil::NotValidName(connStr)) {
            LogError("Error: invalid connection string: '" + connStr + "'. tablename='" + tablename + "'");
            return nullptr;
        }

        const auto key = connStr + tablename;
        std::lock_guard<std::mutex> lock(tablemutex);

        auto ctIter = cloudTableMap.find(key);
        if (ctIter != cloudTableMap.end()) {
            trace.NOTE("Found table object in cache. tablename='" + tablename + "'");
            tableObj = ctIter->second;
        }
        else {
            trace.NOTE("Create new cloud_table for '" + tablename + "' with connection string='" + connStr + "'.");
            tableObj = std::make_shared<cloud_table>(
                cloud_storage_account::parse(connStr)
                .create_cloud_table_client()
                .get_table_reference(tablename)
                );


            cloudTableMap[key] = tableObj;
        }
    }
    catch(const std::exception& e)
    {
        LogError("Error: XTableHelper::CreateTable(" + tablename + "): unexpected std::exception: " + string(e.what()) );
    }
    catch(...)
    {
        LogError("Error: XTableHelper::CreateTable(" + tablename + "): unexpected exception");
    }

    return tableObj;
}


/*
  Handle storage exception. Return true if the execution can be retried. Return false if no value to retry.
 
  By default, not report error when an exception occurs. 
  
  The default behavior is to retry, except the following cases, where the HTTP status code is:
  - BadRequest 400: bad API request. report error. (ex: bad credential)
  - NotFound 404 : table not found. report error.
  - Forbidden 403 : permission denied. report error.
  - Conflict 409 : data already uploaded or duplicates found. 
    If this is the first time, report error. if not first time, shouldn't report error.
 */
bool XTableHelper::HandleStorageException(const string & tablename, const storage_exception& e,
					  size_t * pnerrs, bool isFirstTime, bool * isNoSuchTable)
{
	Trace trace(Trace::XTable, "HandleStorageException");

	bool retryableErr = true;    
	bool suppressErrorMsg = false;

	trace.NOTE(std::string("Storage exception: ") + e.what());

	auto msg = std::string(e.what()) + "\n";
	
	request_result result = e.result();
	storage_extended_error err = result.extended_error();
	if (!err.message().empty())
	{
		msg += err.message();
		trace.NOTE("Extended info: " + err.message());
	}
                
	// the retryable API is not accurate (ex for a client timeout, which retry may work, but retryable
	// is still false. so not use it as of 10/17/14.)
	// bool retryable1 = e.retryable();
	// msg += ustring("exception is retryable? = ") + std::to_string(retryable1);

	web::http::status_code httpcode = result.http_status_code();
    	trace.NOTE("HTTP status " + std::to_string(httpcode));
	msg += "\nStatusCode=" + std::to_string(httpcode);

	bool isErr = false;

	{
	    using web::http::status_codes;
	    if (httpcode == status_codes::NotFound && isNoSuchTable) {
	    	*isNoSuchTable = true;
		// By handing us a valid isNoSuchTable ptr, caller has indicated
		// a desire to handle the No Such Table error directly.
		suppressErrorMsg = true;
	    }
	    if (httpcode == status_codes::NotFound || httpcode == status_codes::BadRequest || httpcode == status_codes::Forbidden) {
		    isErr = true;
	    } else if (httpcode == status_codes::Conflict) {
		    retryableErr = false;
		    if (isFirstTime) {
			    isErr = true;
		    }
	    }
	}

	if (isErr) { 
		if (!suppressErrorMsg) {
			LogError("Azure Storage Exception for table \"" + tablename + "\": " + msg);
		}
		retryableErr = false;
		if (pnerrs) (*pnerrs)++;
	}
	if (!retryableErr) {
		trace.NOTE("Status code " + std::to_string(httpcode) + " is not retryable. Abort further retry.");
	}

	return retryableErr;
}

void XTableHelper::CreateRequestOperation(table_request_options& requestOpt) const
{      
    exponential_retry_policy retry_policy(
          std::chrono::seconds(XTableConstants::SDKRetryPolicyInterval()), XTableConstants::SDKRetryPolicyLimit());
    requestOpt.set_retry_policy(retry_policy);

    requestOpt.set_server_timeout(std::chrono::seconds(XTableConstants::DefaultOpTimeout()));
    requestOpt.set_maximum_execution_time(std::chrono::seconds(XTableConstants::InitialOpTimeout()));

    requestOpt.set_payload_format(table_payload_format::json_no_metadata);
}

void XTableHelper::CreateOperationContext(operation_context& c) const
{    
    std::string id = utility::uuid_to_string(utility::new_uuid());
    c.set_client_request_id(id);
}

/*
 Error level logging. This is to isolate XTableHelper logging.
 */
void XTableHelper::LogError(const std::string & msg) const
{    
    auto msg2 = MdsdUtil::GetTid() + ": " + msg;
    Logger::LogError(msg2);
}

// vim: se sw=4 :	// Would prefer 8, but... c'est la vie
