// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _XTABLEHELPER_HH_
#define _XTABLEHELPER_HH_

#include <unordered_map>
#include <string>
#include "was/storage_account.h"
#include "was/table.h"
#include <mutex>
#include <memory>

/*
  This class manages storage table operations. Because same event can be uploaded
  to multiple tables, instead of creating new table, uploading, then deleting it, each new
  table object will be saved in cache. All tables are freed at final destruction time.
 */

class XTableHelper
{
public:    
    static XTableHelper* GetInstance();

    // disable copy and move contructors
    XTableHelper(XTableHelper&& h) = delete;
    XTableHelper& operator=(XTableHelper&& h) = delete;

    XTableHelper(const XTableHelper&) = delete;
    XTableHelper& operator=(const XTableHelper &) = delete;

    // create a new cloud table using connection string (ex: AccountName/Key, or SAS Key)
    // The table will be stored in a cache for future fast reference.
    // tablename: the actual tablename, not a URI.
    std::shared_ptr<azure::storage::cloud_table> CreateTable(const std::string& tablename, const std::string& connStr);

    // Handle storage exception. Return true if the execution can be retried. Return false 
    // if no value to retry. Return the number of errors found by pnerrs. If isFirstTry is
    // true, it means this is the first time to run the upload operation on this dataset.
    // Only updates *pnerrs and *isNoSuchTable if those pointers are not nullptr.
    bool HandleStorageException(const std::string& tablename, const azure::storage::storage_exception& e,
    				size_t * pnerrs, bool isFirstTry, bool * isNoSuchTable);

    // Create a new request operation object.
    void CreateRequestOperation(azure::storage::table_request_options& options) const;

    // Create a new operation context object.
    void CreateOperationContext(azure::storage::operation_context & context) const;

private:
    XTableHelper();
    ~XTableHelper();

    // Log error message. This function is to make isolated test easiler.
    void LogError(const std::string& msg) const;

    // This will store all the created cloud_table objects. Key=tableUri;
    std::unordered_map<std::string, std::shared_ptr<azure::storage::cloud_table>> cloudTableMap;
    std::mutex tablemutex;
};


#endif // _XTABLEHELPER_HH_
