// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _XTABLEREQUEST_HH_
#define _XTABLEREQUEST_HH_
#include <string>
#include <vector>
#include <cstdlib>
#include <memory>
#include <was/storage_account.h>
#include <was/table.h>
#include <boost/system/error_code.hpp>

class XTableRequest
{
public:
	XTableRequest(const std::string& connStr, const std::string& tablename);

	bool AddRow(const azure::storage::table_entity &row);
	static void Send(std::unique_ptr<XTableRequest> req);
	size_t Size() { return _rowCount; }

private:
	std::shared_ptr<azure::storage::cloud_table> _table;
	std::string _tablename;
	azure::storage::table_batch_operation _batchOperation;
	azure::storage::table_request_options _requestOptions;
	azure::storage::operation_context _context;

	size_t _rowCount;
	bool _useUpsert;

	static void DoWork(std::shared_ptr<XTableRequest> req, const boost::system::error_code&);
	static void DoContinuation(std::shared_ptr<XTableRequest> req, pplx::task<std::vector<azure::storage::table_result> > t);
};

#endif // _XTABLEREQUEST_HH_

// vim: se sw=8 :
