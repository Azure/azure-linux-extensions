// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XTableRequest.hh"
#include "XTableConst.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "XTableHelper.hh"
#include "MdsdMetrics.hh"
#include <algorithm>
#include <sstream>

XTableRequest::XTableRequest(const std::string& connStr, const std::string& tablename)
	: _tablename(tablename), _rowCount(0)
{
	Trace trace(Trace::XTable, "XTR Constructor");

	auto helper = XTableHelper::GetInstance();

	_table = helper->CreateTable(tablename, connStr);
	if (!_table) {
		std::ostringstream msg;
		msg << "CreateTable(" << tablename << ", '" << connStr << "') returned nullptr";
		trace.NOTE(msg.str());
		throw std::runtime_error(msg.str());
	}

	helper->CreateRequestOperation(_requestOptions);
	helper->CreateOperationContext(_context);

	_useUpsert = (tablename == "SchemasTable"); // Ugh - such a hack
}

bool
XTableRequest::AddRow(const azure::storage::table_entity & row)
{
	Trace trace(Trace::XTable, "XTR::AddRow");
	if (_rowCount == XTableConstants::MaxItemPerBatch()) {
		trace.NOTE("Batch is already full; ignoring row");
		return false;
	}

	if (_useUpsert) {
		_batchOperation.insert_or_replace_entity(row);
	} else {
		_batchOperation.insert_entity(row);
	}
	_rowCount++;

	return true;
}

/*static*/ void
XTableRequest::Send(std::unique_ptr<XTableRequest> req)
{
	Trace trace(Trace::XTable, "XTR::Send");
	req->_rowCount = req->_batchOperation.operations().size();

	MdsdMetrics::Count("XTable_send");
	MdsdMetrics::Count("XTable_rowsSent", req->_rowCount);
	if (req->_rowCount == 0) {
		trace.NOTE("Shortcut completion: zero row count");
		return;
	}

	// Need to convert the unique_ptr to shared_ptr for lambda capture inside
	XTableRequest::DoWork(std::shared_ptr<XTableRequest>(req.release()), boost::system::error_code());
}

/*static*/ void
XTableRequest::DoWork(std::shared_ptr<XTableRequest> req, const boost::system::error_code &error)
{
	Trace trace(Trace::XTable, "XTR::DoWork");

	if (error) {
		std::ostringstream msg;
		msg << "DoWork() observed error " << error << " from previous task";
		trace.NOTE(msg.str());
		Logger::LogError(msg.str());
		return;
	}

	req->_table->execute_batch_async(req->_batchOperation, req->_requestOptions, req->_context)
	.then([req](pplx::task<std::vector<azure::storage::table_result> > t) { DoContinuation(req, t); })
	.then([=](pplx::task<void> previous_task) {
		try {
			previous_task.wait();
		}
		catch (std::exception & e) {
			MdsdMetrics::Count("XTable_failedGeneralException");
			std::ostringstream msg;
			msg << "Writing to table '" << req->_tablename << "' "
				<< "caught exception: " << e.what();
			Logger::LogError("XTR::DoWork(): " + msg.str());
		}
		catch(...) {
			MdsdMetrics::Count("XTable_failedUnknownException");
			Logger::LogError("XTR::DoWork() caught unknown exception.");
		}
	});
}

/*static*/ void
XTableRequest::DoContinuation(std::shared_ptr<XTableRequest> req, pplx::task<std::vector<azure::storage::table_result> > t)
{
	Trace trace(Trace::XTable, "XTR::DoContinuation");
	size_t errcount = 0;
	try
	{
		t.wait();
		for (const auto &result : t.get() ) {
			if (result.http_status_code() != web::http::status_codes::NoContent) {
				std::ostringstream msg;
				msg << "Unexpected HTTP status " << result.http_status_code() << " when writing to " << req->_tablename;
				trace.NOTE(msg.str());
				Logger::LogError(msg.str());
				errcount++;
			}
		}
		if (errcount) {
			std::ostringstream msg;
			msg << "Total of " << errcount << ((errcount==1)?"error":"errors") << " while writing to " << req->_tablename;
			Logger::LogError(msg.str());
			MdsdMetrics::Count("XTable_completeWithErrors");
			trace.NOTE("Completed but some rows not successful");
		}
		else {
			MdsdMetrics::Count("XTable_complete");
			trace.NOTE("Complete");
		}
		MdsdMetrics::Count("XTable_rowsSuccess", req->_rowCount - std::min(errcount, req->_rowCount));
	}
	catch (azure::storage::storage_exception & e) {
		trace.NOTE("Caught storage exception for table " + req->_tablename);
		bool isNoSuchTable = false;
		XTableHelper::GetInstance()->HandleStorageException(req->_tablename, e, &errcount,
								true, &isNoSuchTable);
		if (isNoSuchTable) {
			// Table doesn't exist. Let's see if we can create it.
			trace.NOTE("Trying to create table " + req->_tablename);
			MdsdMetrics::Count("XTable_tableCreate");
			req->_table->create_if_not_exists_async(req->_requestOptions, req->_context)
			  .then([req](pplx::task<bool> t) {
				Trace trace(Trace::XTable, "XTR Create Table lambda");
				try
				{
					t.wait();
					(void) t.get();		// Don't care if it was already created
					// If we get here, the table exists; let's retry the initial operation
					MdsdMetrics::Count("XTable_retries");
					XTableRequest::DoWork(req, boost::system::error_code());
					return;
				}
				catch (azure::storage::storage_exception & e) {
					// Just emit the necessary error messages
					(void)XTableHelper::GetInstance()
						->HandleStorageException(req->_tablename, e, nullptr, true, nullptr);
				}
				catch (std::exception& e) {
					std::string msg = "While trying to create table " + req->_tablename
							+ " Caught exception: " + e.what();
					trace.NOTE(msg);
					Logger::LogError(msg);
				}
				catch (...) {
					std::string msg = "While trying to create table " + req->_tablename
							+ " Caught unknown exception.";
					trace.NOTE(msg);
					Logger::LogError(msg);
				}
			});
			return;
		}
	}
	catch (std::exception & e) {
		MdsdMetrics::Count("XTable_failedGeneralException");
		std::ostringstream msg;
		msg << "Caught exception: " << e.what();
		trace.NOTE(msg.str());
		Logger::LogError("XTR::DoContinuation(): " + msg.str());
	}
	catch (...) {
		MdsdMetrics::Count("XTable_failedUnknownException");
		trace.NOTE("Caught unknown exception.");
		Logger::LogError("XTR::DoContinuation() caught unknown exception.");
	}
}

// vim: se sw=8 :
