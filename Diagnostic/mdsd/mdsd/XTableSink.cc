// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "XTableSink.hh"

#include <iterator>
#include <sstream>

#include "CanonicalEntity.hh"
#include "Engine.hh"
#include "MdsdConfig.hh"
#include "Credentials.hh"
#include "Utility.hh"
#include "RowIndex.hh"
#include "Trace.hh"
#include "MdsdMetrics.hh"
#include "XTableRequest.hh"
#include "StoreType.hh"

#include "stdafx.h"
#include "was/table.h"
#include "was/common.h"

using std::string;
using azure::storage::entity_property;

XTableSink::XTableSink(MdsdConfig* config, const MdsEntityName &target, const Credentials* c)
  : IMdsSink(StoreType::Type::XTable), _config(config), _target(target), _creds(c)
{
	Trace trace(Trace::XTable, "XTS::Constructor");

	if (!target.IsSchemasTable()) {
		// Build the identity columns metadata only once
		// Similarly, compute the partition data only once.
		// SchemasTable has no identity columns (in this sense) and does partitioning differently
		config->GetIdentityColumnValues(std::back_inserter(_identityColumns));
		std::vector<string> identValues;
		identValues.reserve(_identityColumns.size());
		for (const ident_col_t& idpair : _identityColumns) {
			identValues.push_back(idpair.second);
		}

		_identColumnString = MdsdUtil::Join(identValues, "___");
		unsigned long long N = MdsdUtil::EasyHash(_identColumnString) % (unsigned long long)(_config->PartitionCount());
		_N = MdsdUtil::ZeroFill(N, 19);
	}
	_estimatedBytes = 0;
}

void
XTableSink::ComputeConnString()
{
	Trace trace(Trace::XTable, "XTS::ComputeConnString");

	if (_creds->ConnectionString(_target, Credentials::ServiceType::XTable, _fullTableName, _connString, _rebuildTime) ) {
		if (trace.IsActive()) {
			std::ostringstream msg;
			msg << _fullTableName << "=[" << _connString << "] expires " << _rebuildTime;
			trace.NOTE(msg.str());
		}
	} else {
		Logger::LogError("Couldn't construct connection string for table " + _target.Name());
	}
}

XTableSink::~XTableSink()
{
	Trace trace(Trace::XTable, "XTS::Destructor");
}

// Convert the CanonicalEntity to a table_entity and add it to our internal request. Flush
// the request if it fills up.
//
// Note that AddRow() doesn't keep the CanonicalEntity; we copy anything we need from it.
void
XTableSink::AddRow(const CanonicalEntity &row, const MdsTime& qibase)
{
	Trace trace(Trace::XTable, "XTS::AddRow");

	// If this row is for a different partition, flush what we have and track the new partition
	if (row.PartitionKey() != _pkey) {
		Flush();
		_pkey = row.PartitionKey();
	}

	// If we have no in-progress request, either because we just flushed or because we're just
	// starting up, make one.
	if (! _request) {
		try {
			ComputeConnString();
			_request.reset(new XTableRequest(_connString, _fullTableName));
		}
		catch (std::exception &ex) {
			std::ostringstream msg;

			msg << "Exception (" << ex.what() << ") caught while creating new XTableRequest; dropping row";
			trace.NOTE(msg.str());
			Logger::LogError(msg.str());
			MdsdMetrics::Count("Dropped_Entities");
			return;
		}
	}

	azure::storage::table_entity e { _pkey, row.RowKey() };
	azure::storage::table_entity::properties_type& properties = e.properties();
	size_t byteCount = 2 * (_pkey.length() + row.RowKey().length()) + 4;
	bool oversize = false;

	for (const auto & col : row) {
		// col is pair<string name, MdsValue* val>
		auto namesize = 2 * col.first.length();
		byteCount += namesize;		// Account for the column name, which is stored in the entity in XStore
		switch((col.second)->type) {
			case MdsValue::MdsType::mt_bool:
				properties[col.first] = entity_property((col.second)->bval);
				byteCount += 1;
				break;
			case MdsValue::MdsType::mt_wstr:
				{
					properties[col.first] = entity_property(*((col.second)->strval));
					auto colsize = 2 * ((col.second)->strval->length()) + 2;
					byteCount += colsize;
					if (colsize + namesize > 65536) {	// XStore max attribute size is 64Ki
						std::ostringstream msg;
						msg << "Column " << col.first << " oversize: colsize " << colsize
							<< " namesize " << namesize;
						trace.NOTE(msg.str());
						oversize = true;
					}
				}
				break;
			case MdsValue::MdsType::mt_float64:
				properties[col.first] = entity_property((col.second)->dval);
				byteCount += 8;
				break;
			case MdsValue::MdsType::mt_int32:
				properties[col.first] = entity_property((int32_t)(col.second)->lval);
				byteCount += 4;
				break;
			case MdsValue::MdsType::mt_int64:
				properties[col.first] = entity_property((int64_t)(col.second)->llval);
				byteCount += 8;
				break;
			case MdsValue::MdsType::mt_utc:
				properties[col.first] = entity_property((col.second)->datetimeval);
				byteCount += 8;
				break;
		}
	}

	if (oversize || (byteCount > 1024*1024)) {	// XStore max table size is 1024Ki
		trace.NOTE("Entity or column too large - dropped");
		std::ostringstream msg;
		msg << "Dropping oversize entity: " << row;
		Logger::LogWarn(msg.str());
		MdsdMetrics::Count("Dropped_Entities");
		MdsdMetrics::Count("Overlarge_Entities");
		return;
	}

	if ((_estimatedBytes + byteCount) > 4000000) {
		trace.NOTE("Batch would be too big; flushing before adding this entity");
		Flush();
		try {
			ComputeConnString();
			_request.reset(new XTableRequest(_connString, _fullTableName));
		}
		catch (std::exception & ex) {
			std::ostringstream msg;

			msg << "Exception (" << ex.what() << ") caught while creating new XTableRequest; dropping row";
			trace.NOTE(msg.str());
			Logger::LogError(msg.str());
			MdsdMetrics::Count("Dropped_Entities");
			return;
		}
	}
	_request->AddRow(e);
	_estimatedBytes += byteCount;

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "We have " << _request->Size() << " rows";
		trace.NOTE(msg.str());
	}
	if (_request->Size() == 100) {
		Flush();
	}
}

// Flush any data we're holding. We might never have allocated a request, or it might
// be empty, or we might have data.
// Post-condition: _request is nullptr. Next call to AddRow() will create a new request on demand.
void
XTableSink::Flush()
{
	Trace trace(Trace::XTable, "XTS::Flush");

	if (!_request) {
		// First time through. Just make the post-condition true
		trace.NOTE("Null _request; no action.");
	} else {
		if (_request->Size() > 0) {
			// Detach the request and send it. Send() is fire-and-forget; the request object
			// is responsible for deleting itself after that point.
			trace.NOTE("Writing to " + _fullTableName + " with connection string " + _connString);
			XTableRequest::Send(std::move(_request));
		} else {
			// Since we create these on demand, this really shouldn't happen.
			trace.NOTE("Empty _request; no action (deleting).");
		}
		_request.reset();
		_estimatedBytes = 0;
	}
}

// vim: se sw=8 :
