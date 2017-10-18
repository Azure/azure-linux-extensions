// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "LocalSink.hh"

#include <iterator>
#include <sstream>
#include <algorithm>

#include "CanonicalEntity.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"
#include "RowIndex.hh"
#include "Trace.hh"
#include "MdsdMetrics.hh"
#include "StoreType.hh"
#include "SchemaCache.hh"
#include "Logger.hh"
#include "EventHubUploaderId.hh"
#include "EventHubType.hh"
#include "EventHubUploaderMgr.hh"

// Class statics
//
// Table of local tables and a mutex to protect it. The map is altered only
// while loading configurations, but that can happen in parallel with incoming events.
// It may be that the global table is referenced only during config load, in which case
// the mutex won't be needed.
//
// These are on the heap because there's no way to control the order of destruction of
// global static objects declared in separate compilation units. The Batch class contains
// a pointer to a sink; Batch instances in the global static MdsdConfig::_localBatches
// BatchSet all point to LocalSink objects. If the LocalSink::_localTables map were a
// global static, it might be destroyed at program-exit before the static _localBatches
// was destroyed. In that case, when the Batch destructor deletes its LocalSink, the
// LocalSink destructor tries to remove the object from the _localTables map which has
// already been destroyed.

std::mutex* LocalSink::_ltMutex { nullptr };
std::map<const std::string, LocalSink*>* LocalSink::_localTables { nullptr };

void
LocalSink::Initialize()
{
	if (_ltMutex == nullptr) {
		_ltMutex = new std::mutex;
		_localTables = new std::map<const std::string, LocalSink*>;
	}
}

LocalSink::LocalSink(const std::string &name)
  : IMdsSink(StoreType::Type::Local), _name(name), _schemaId(0)
{
	Trace trace(Trace::Local, "LocalSink::Constructor");

	std::unique_lock<std::mutex> lock(*_ltMutex);
	auto result = _localTables->insert(std::pair<const std::string, LocalSink*>(_name, this));
	lock.unlock();
	if (!(result.second)) {
		throw std::invalid_argument("Duplicate local table name");
	}
}

LocalSink::~LocalSink()
{
	Trace trace(Trace::Local, "LocalSink::Destructor");

	std::lock_guard<std::mutex> lock(*_ltMutex);
	_localTables->erase(_name);
}

void
LocalSink::AllocateSchemaId()
{
	_schemaId = SchemaCache::Get().GetId();
}

LocalSink*
LocalSink::Lookup(const std::string& name)
{
	Trace trace(Trace::Local, "LocalSink::Lookup");
	trace.NOTE("Looking for LocalSink " + name);
	std::lock_guard<std::mutex> lock(*_ltMutex);
	auto iter = _localTables->find(name);
	if (iter == _localTables->end()) {
		trace.NOTE("Not found");
		return nullptr;
	} else {
		trace.NOTE("Found it");
		return iter->second;
	}
}

// Copy the CE before adding it
void
LocalSink::AddRow(const CanonicalEntity &row, const MdsTime& )
{
	Trace trace(Trace::Local, "LocalSink::AddRow(CE)");

	std::shared_ptr<CanonicalEntity> item;

	try {
		item.reset(new CanonicalEntity(row));
	}
	catch (const std::exception& ex) {
		Logger::LogError("Exception copying item to insert into LocalSink " + _name + ": " + ex.what());
		return;
	}
	AddRow(item);
}

// This version of AddRow assumes it can share the CE.
void
LocalSink::AddRow(std::shared_ptr<CanonicalEntity> item)
{
	Trace trace(Trace::Local, "LocalSink::AddRow(shared CE)");
	size_t nEvents = 0;
	try {
		// Add row to event collection, ordered by the PreciseTime() in the item.
		// If retention period is zero, there are no downstream consumers; don't even bother
		// adding the item to the list. This behavior should change when local sinks are persisted;
		// the item should be written to the disk. If some fraction of a local sink is retained in
		// memory (as a performance optimization), that should not happen if RetentionPeriod() == 0
		if (RetentionPeriod()) {
			std::lock_guard<std::mutex> lock(_mutex);
			_events.emplace_hint(_events.end(), item->PreciseTime(), item);
			nEvents = _events.size();
		}

		if (!_ehpubMonikers.empty() && CanonicalEntity::SourceType::Ingested == item->GetSourceType()) {
			SendToEventPub(item);
		}
	}
	catch (const std::exception& ex) {
		Logger::LogError("Exception adding item to LocalSink " + _name + ": " + ex.what());
		return;
	}
	TRACEINFO(trace, "LocalSink " << _name << " now has " << nEvents << " rows");
}

// Copy the value (shared_ptr<CanonicalEntity>) from the map elements in the range. This increases the
// refcount on all the shared pointers; it doesn't actually copy the CanonicalEntity objects.
// *** Must be called with _mutex already held ***
LocalSink::vector_type
LocalSink::ExtractRange(LocalSink::iterator start, LocalSink::iterator end)
{
	LocalSink::vector_type extract;
	typedef LocalSink::iterator::value_type value_type;

	if (start != end) {
		try {
			auto count = std::distance(start, end);
			extract.reserve(count);
			std::for_each(start, end, [&extract](value_type& val){extract.push_back(val.second);});
		}
		catch (const std::exception& ex) {
			Logger::LogError("Exception in ExtractRange on " + _name + ": " + ex.what());
		}
	}
	return extract;
}

void
LocalSink::Flush()
{
	Trace trace(Trace::Local, "LocalSink::Flush");

	// The instance knows the longest timespan we'll ever be asked for (gap between
	// Foreach()'s begin and delta parameters. Just call Flush(now - span).
	// We actually double the span for safety's sake.

	Flush(MdsTime::Now() - RetentionPeriod() - RetentionPeriod());
}

void
LocalSink::Flush(const MdsTime& when)
{
	Trace trace(Trace::Local, "LocalSink::Flush(when)");
	TRACEINFO(trace, "Flushing items older than " << when << " from LocalSink " << _name);

	LocalSink::vector_type scrubList;
	try {
		std::lock_guard<std::mutex> lock(_mutex);
		iterator rangeEnd = _events.lower_bound(when);
		if (rangeEnd == _events.begin()) {
			TRACEINFO(trace, "Nothing to remove from LocalSink " << _name);
			return;
		}
		scrubList = ExtractRange(_events.begin(), rangeEnd);

		// Erase all the entries from the multimap (won't destroy the CEs) and release the lock
		TRACEINFO(trace, "Removing " << scrubList.size() << " items from " << _name);
		_events.erase(_events.begin(), rangeEnd);
	}
	catch (const std::exception& ex) {
		Logger::LogError("Exception while removing range from " + _name + ": " + ex.what());
	}

	// Now we can delete these without blocking everyone else waiting on the sink. It is very
	// likely the shared_ptrs in this list have a refcount of 1 and will thus the CEs will be destructed.
	// By explicitly clearing the scrubList, we can determine how much real time is required
	// to destroy all those objects (time between this trace message and the "Leaving" message).
	TRACEINFO(trace, "Destroying " << scrubList.size() << " items removed from " << _name);
	scrubList.clear();
}

// Extract each event in the [begin, begin+delta) range, then invoke the function on each extracted event.
// Release the shared ptr for the extracted events as we go, amortizing heap operations over time. A large
// extract may be the last holder of a reference to a CE, so releasing as-we-go could make memory available sooner.
void
LocalSink::Foreach(const MdsTime &begin, const MdsTime &delta, const std::function<void(const CanonicalEntity &)>& fn)
{
	Trace trace(Trace::Local, "LocalSink::Foreach");
	TRACEINFO(trace, "begin at " << begin << ", delta " << delta);

	LocalSink::vector_type matchedEvents;
	try {
		std::lock_guard<std::mutex> lock(_mutex);
		matchedEvents = ExtractRange(_events.lower_bound(begin), _events.lower_bound(begin + delta));
	}
	catch (const std::exception& ex) {
		Logger::LogError("Exception while extracting range from " + _name + ": " + ex.what());
		return;
	}

	TRACEINFO(trace, "Extracted " << matchedEvents.size() << " events from " << _name);
	for (auto& eventPtr : matchedEvents) {
		fn(*eventPtr);
		eventPtr.reset();	// Done with this item; if we're the last user, let it go
	}
}

void
LocalSink::SetEventPublishInfo(
	const std::unordered_set<std::string> & monikers,
	std::string eventDuration,
	std::string tenant,
	std::string role,
	std::string roleInstance
	)
{
	if (monikers.empty()) {
		throw std::invalid_argument("SetEventPublishInfo(): moniker cannot be empty.");
	}

	_ehpubMonikers = monikers;
	_eventDuration = std::move(eventDuration);
	_tenant = std::move(tenant);
	_role = std::move(role);
	_roleInstance = std::move(roleInstance);
}

void
LocalSink::SendToEventPub(std::shared_ptr<CanonicalEntity> item)
{
	Trace trace(Trace::Local, "LocalSink::SendToEventPub");
	if (!item) {
		throw std::invalid_argument("LocalSink::SendToEventPub(): CanonicalEntity cannot be nullptr");
	}

	auto jsonData = item->GetJsonRow(_eventDuration, _tenant, _role, _roleInstance);
	if (jsonData.empty()) {
		throw std::runtime_error("LocalSink::SendToEventPub(): failed to get data to publish.");
	}

	mdsd::EventDataT ehdata;
	ehdata.SetData(jsonData);

	auto ehtype = mdsd::EventHubType::Publish;
	for (const auto & moniker : _ehpubMonikers) {
		mdsd::EventHubUploaderMgr::GetInstance().AddMessageToUpload(
			mdsd::EventHubUploaderId(ehtype, moniker, _name),
			std::move(ehdata));
		TRACEINFO(trace, "LocalSink::SendToEventPub: moniker=" << moniker << "; sinkName=" << _name);
	}
}

// vim: se sw=8 :
