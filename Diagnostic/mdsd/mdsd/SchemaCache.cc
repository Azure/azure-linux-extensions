// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "SchemaCache.hh"
#include "Trace.hh"
#include <sstream>
#include "Crypto.hh"

std::mutex SchemaCache::_mutex;
SchemaCache* SchemaCache::_singleton;

SchemaCache& SchemaCache::Get()
{
	Trace trace(Trace::SchemaCache, "SchemaCache::Get");

	// Double-check locking to ensure we instantiate the singleton exactly once.
	// We already needed the mutex for other purposes, so do this manually instead
	// of using std::call_once and std::once_flag.
	if (_singleton == nullptr) {
		_mutex.lock();
		if (_singleton == nullptr) {
			_singleton = new SchemaCache();
			trace.NOTE("Allocating singleton cache");
		}
		_mutex.unlock();
	}

	return *_singleton;
}

// Store the id, move the schema string from the argument into the object, compute the MD5 hash.
// If the caller(s) all along the line enabled move semantics, we should wind up with the schema inside
// this object without any copying.
SchemaCache::Info::Info(SchemaCache::IdType id, std::string schema)
	: _id(id), _schema(std::move(schema)), _md5(Crypto::MD5HashString(_schema))
{
}

std::map<SchemaCache::IdType, SchemaCache::CachedType> &
SchemaCache::Select(Kind kind)
{
	switch(kind)
	{
	case XTable:
		return _XTableCache;
	case Bond:
		return _BondCache;
	default:
		throw std::invalid_argument("Access to SchemaCache of unknown kind");
	}
}

bool
SchemaCache::IsCached(SchemaCache::IdType id, Kind kind) noexcept
{
	Trace trace(Trace::SchemaCache, "SchemaCache::IsCached");
	try {
		std::lock_guard<std::mutex> lock(_mutex);
		bool found = (Select(kind).count(id) > 0);
		if (trace.IsActive()) {
			std::ostringstream msg;
			msg << "Cache(" << kind;
			if (found) {
				msg << ") did ";
			} else {
				msg << ") did not ";
			}
			msg << "contain key " << id;
			trace.NOTE(msg.str());
		}
		return found;
	} catch (std::exception& ex) {
		// We don't cache anything for unknown kinds of schemas
		trace.NOTE(std::string("Exception caught: ") + ex.what());
		return false;
	}
}

SchemaCache::CachedType
SchemaCache::Find(SchemaCache::IdType id, Kind kind)
{
	auto& cache = Select(kind);

	// Lock the map down long enough to copy the result
	std::unique_lock<std::mutex> lock(_mutex);
	auto it = cache.find(id);
	lock.unlock();

	if (it == cache.end()) {
		std::ostringstream msg;
		msg << "SchemaCache(" << kind << ") does not contain id " << id;
		throw std::runtime_error(msg.str());
	}

	return it->second;
}

void
SchemaCache::Evict(SchemaCache::IdType id, Kind kind) noexcept
{
	// Select is not nothrow, but the only exception it throws is one we want
	// to ignore (invalid kind). std::map::erase is nothrow.
	try {
		std::lock_guard<std::mutex> lock(_mutex);
		(void) Select(kind).erase(id);
	}
	catch (...)
	{
	}
}

// Create an info structure by moving the schema into it.
void
SchemaCache::Insert(SchemaCache::IdType id, Kind kind, std::string schema)
{
	Trace trace(Trace::SchemaCache, "SchemaCache::Insert");

	auto entry = std::make_shared<SchemaCache::Info>(id, std::move(schema));
	auto & cache = Select(kind);
	std::lock_guard<std::mutex> lock(_mutex);
	cache[id] = std::move(entry);
	if (trace.IsActive()) {
		std::ostringstream msg;
		msg << "Added id " << id << " to cache of type " << kind;
		trace.NOTE(msg.str());
	}
}

std::ostream&
operator<<(std::ostream& strm, SchemaCache::Kind kind)
{
	switch(kind)
	{
	case SchemaCache::Kind::XTable:
		strm << "XTable";
		break;
	case SchemaCache::Kind::Bond:
		strm << "Bond";
		break;
	default:
		strm << "!Unknown!";
		break;
	}
	return strm;
}

#ifdef ENABLE_TESTING

void
TEST__SchemaCache_Reset()
{
	if (SchemaCache::_singleton) {
		delete SchemaCache::_singleton;
		SchemaCache::_singleton = nullptr;
	}
}

std::map<SchemaCache::IdType, SchemaCache::CachedType>&
TEST__SchemaCache_Select(SchemaCache::Kind kind)
{
	return SchemaCache::Get().Select(kind);
}

#endif // ENABLE_TESTING

// vim: set ai sw=8 :
