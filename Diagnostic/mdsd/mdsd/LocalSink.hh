// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _LOCALSINK_HH_
#define _LOCALSINK_HH_

#include "IMdsSink.hh"
#include <map>
#include <memory>
#include <functional>
#include <string>
#include <mutex>
#include <unordered_set>
#include "MdsTime.hh"
#include "MdsEntityName.hh"
#include "CanonicalEntity.hh"
#include "SchemaCache.hh"

class LocalSink : public IMdsSink
{
public:
	typedef std::multimap<const MdsTime, std::shared_ptr<CanonicalEntity>> map_type;
	typedef std::vector<std::shared_ptr<CanonicalEntity>> vector_type;
	typedef map_type::iterator iterator;

	LocalSink(const std::string&);
	virtual ~LocalSink();

	virtual bool IsLocal() const { return true; }
	virtual void AddRow(const CanonicalEntity&, const MdsTime&);
	virtual void Flush();

	// An ingested event goes to precisely one LocalSink; this method
	// lets us avoid copying the CE upon ingest
	void AddRow(std::shared_ptr<CanonicalEntity>);

	void Flush(const MdsTime &when);
	void Foreach(const MdsTime &when, const MdsTime &delta, const std::function<void(const CanonicalEntity &)>&);

	void AllocateSchemaId();
	SchemaCache::IdType SchemaId()		  { return _schemaId; }

	static LocalSink * Lookup(const std::string& name);

	static void Initialize();

	void SetEventPublishInfo(const std::unordered_set<std::string> & monikers,
		std::string eventDuration,
		std::string tenant,
		std::string role,
		std::string roleInstance);

private:
	vector_type ExtractRange(iterator start, iterator end);
	void SendToEventPub(std::shared_ptr<CanonicalEntity> item);

	map_type _events;
	const std::string _name;

	// Applies only to local sinks which directly receive json external data; derived
	// local tables will have a 0 _schemaId, and so will sinks that receive BOND and dynamic json external data.
	SchemaCache::IdType _schemaId;

	std::mutex _mutex;

	static std::map<const std::string, LocalSink*>* _localTables;
	static std::mutex* _ltMutex;

	// event publishing information
	std::unordered_set<std::string> _ehpubMonikers;
	std::string _eventDuration;
	std::string _tenant;
	std::string _role;
	std::string _roleInstance;
};

#endif // _LOCALSINK_HH_

// vim: se sw=8 :
