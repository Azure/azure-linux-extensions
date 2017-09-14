// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Batch.hh"
#include "MdsdConfig.hh"
#include "Credentials.hh"
#include "MdsEntityName.hh"
#include "CanonicalEntity.hh"
#include "IMdsSink.hh"
#include "Trace.hh"
#include "Logger.hh"
#include "Utility.hh"
#include <sstream>

using std::string;

Batch::Batch(MdsdConfig* config, const MdsEntityName& target, const Credentials* creds, int interval)
  : _config(config), _batchQIBase(0), _interval(interval), _sink(IMdsSink::CreateSink(config, target, creds)), _dirty(false)
{
	Trace trace(Trace::Batching, "Batch constructor");
	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Created batch " << this << " (eventName " << target << " QI " << interval << ")";
		trace.NOTE(msg.str());
	}
	_sink->ValidateAccess();
}

void
Batch::AddRow(const CanonicalEntity & row)
{
	Trace trace(Trace::Batching, "Batch::AddRow");

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Batch " << this << " add CE " << row;
		trace.NOTE(msg.str());
	}

	MdsTime qibase = row.GetPreciseTimeStamp().Round(_interval);

	std::lock_guard<std::recursive_mutex> lock(_mutex);
	// If the Query Interval Base has changed, then flush the batch.
	if (qibase != _batchQIBase) {
		if (trace.IsActive()) {
			std::ostringstream msg;
			msg << "Query Interval Base changed from " << _batchQIBase << " to " << qibase;
			trace.NOTE(msg.str());
		}
		_sink->Flush();
		_batchQIBase = qibase;
	}

	_sink->AddRow(row, qibase);	// May cause flush...

	MarkTime();
}

// Add a row to a batch destined for SchemasTable in some storage acct. This is a helper function
// for building these rows correctly.
void
Batch::AddSchemaRow(const MdsEntityName &target, const string &hash, const string &schema)
{
	Trace trace(Trace::Batching, "Batch::AddSchemaRow");
	CanonicalEntity row(3);

	row.AddColumn("PhysicalTableName", target.Basename());
	row.AddColumn("MD5Hash", hash);
	row.AddColumn("Schema", schema);

	AddRow(row);
}

void
Batch::Flush()
{
	Trace trace(Trace::Batching, "Batch::Flush");
	
	if (IsClean())
		return;

	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Batch " << this;
		trace.NOTE(msg.str());
	}

	std::lock_guard<std::recursive_mutex> lock(_mutex);
	MarkFlushed();
	_sink->Flush();
}

Batch::~Batch()
{
	Trace trace(Trace::Batching, "Batch::~Batch");
	if (IsDirty())
		Flush();

	delete _sink;
}

bool
Batch::HasStaleData() const
{
	Trace trace(Trace::Batching, "Batch::HasStaleData");
	// I want data to not linger past the end of the *next* QI. If the QI size is 5 minutes and data is
	// written at 00:01:00, that data becomes stale at 00:10:00.

	if (IsClean())
		return false;

	MdsTime trigger = (MdsTime::Now() - _interval).Round(_interval);
	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "_lastAction=" << _lastAction << " _interval=" << _interval << " trigger=" << trigger;
		trace.NOTE(msg.str());
	}
	return (_lastAction < trigger);
}


std::ostream&
operator<<(std::ostream& os, const Batch& batch)
{
	os << &batch << " (QIBase " << batch._batchQIBase << ", Interval " << batch._interval << ", Sink " << batch._sink << ")";
	return os;
}

Batch*
BatchSet::GetBatch(const MdsEntityName &target, int interval)
{
	Trace trace(Trace::Batching, "BatchSet::GetBatch");

	auto creds = target.GetCredentials();
	key_t key = std::make_pair(target.Basename(), creds);
	std::ostringstream keystring;

	if (trace.IsActive()) {
		keystring << "<" << target.Basename() << ", 0x" << creds << ">";
	}

	std::lock_guard<std::mutex> lock(_mutex);	// Lock held until this function returns

	std::map<key_t, Batch*>::iterator iter = _map.find(key);

	if (iter != _map.end()) {
		trace.NOTE("Found batch for " + keystring.str());
		return iter->second;
	}

	trace.NOTE("Creating batch for " + keystring.str());

	std::ostringstream msg;
	// Bug 3532559: Batch constructor can fail if XTableSink constructor fails while
	// creating an XTableRequest. So wrap the constructor in a try/catch block.
	try {
		Batch *batch = new Batch(_config, target, creds, interval);
		if (trace.IsActive()) {
			std::ostringstream msg;
			msg << "New batch " << *batch;
			trace.NOTE(msg.str());
		}
		_map[key] = batch;
		return batch;
	}
	catch (const std::exception& e) {
		msg << "GetBatch(" << target << ") failed to create new batch for " << keystring.str() << ": " << e.what();
	}
	catch (...) {
		msg << "GetBatch(" << target << ") caught unknown exception";
	}
	// If we got here, we caught an exception and already created the error message
	Logger::LogError(msg.str());
	trace.NOTE(msg.str());
	return nullptr;
}

void
BatchSet::Flush()
{
	Trace trace(Trace::Batching, "BatchSet::Flush");
	// Walk the _map and flush all the dirty Batches
	for (const auto &iter : _map) {
		if (iter.second->IsDirty()) {
			iter.second->Flush();
		}
	}
}

void
BatchSet::FlushIfStale()
{
	Trace trace(Trace::Batching, "BatchSet::FlushIfStale");
	// Walk the _map and flush all the Batches
	for (const auto &item : _map) {
		if (item.second->HasStaleData()) {
			item.second->Flush();
		}
	}
}

BatchSet::~BatchSet()
{
	Trace trace(Trace::Batching, "BatchSet::~BatchSet");
	// Walk the _map and delete all the Batches; deleting them will Flush() them first
	for (auto &iter : _map) {
		delete iter.second;
	}
}

// vim: se sw=8 :
