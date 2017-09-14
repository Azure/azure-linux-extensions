// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CANONICALENTITY_HH_
#define _CANONICALENTITY_HH_

#include <string>
#include <utility>
#include <vector>
#include "MdsValue.hh"
#include "MdsTime.hh"
#include "SchemaCache.hh"
#include <iostream>

// CanonicalEntity is the internal canonical form of an entity to be handed to MDS. This is a middle ground
// between the form in which the information was reported to the daemon (e.g. via JSON event, OMI query, etc.)
// and the form required for transmission to the actual MDS data sync (Storage SDK table row object, compressed
// BOND blob, etc.)
//
// CanonicalEntity is the "owner" of the data handed to it. Once you pass an MdsValue* to AddColumn,
// you should leave it alone (and, especially, do not delete it).
//
// CanonicalEntity objects can be copied until they are added to a batch. Once added to a batch, the object
// might at any instant (and asynchronously) be handed to a transport, which will convert it to the form
// required for transmission to MDS and then delete it. Or it could linger in a local sink and eventually
// make its way into some other batch; later rinse repeat.

class CanonicalEntity
{
	using col_t = std::pair<std::string, MdsValue*>;
	friend std::ostream& operator<<(std::ostream& os, const CanonicalEntity& ce);

public:
	enum class SourceType {
		Ingested,       // created from original ingestion
		Duplicated      // created from duplication (e.g. during pipeline)
	};

	CanonicalEntity() : _timestamp(0), _schemaId(0) { _entity.reserve(16); }
	CanonicalEntity(int n) : _timestamp(0), _schemaId(0) { _entity.reserve(n); }
	CanonicalEntity(const CanonicalEntity& src);
	~CanonicalEntity();

	void AddColumn(const std::string name, MdsValue* val);
    void AddColumnIgnoreMetaData(const std::string name, MdsValue* val);

	std::string PartitionKey() const { return _pkey; }
	std::string RowKey() const { return _rkey; }

	void SetPreciseTime(const MdsTime& t) { _timestamp = t; }

	const MdsTime& GetPreciseTimeStamp() const { return _timestamp; }
	const MdsTime& PreciseTime() const { return _timestamp; }
	time_t GetApproximateTime() const { return _timestamp.to_time_t(); }

	MdsValue* Find(const std::string &name) const;

	void SetSchemaId(SchemaCache::IdType id) { _schemaId = id; }
	SchemaCache::IdType SchemaId() const { return _schemaId; }

	// Convenience functions
	void AddColumn(const std::string name, const std::string& val)  { AddColumn(name, new MdsValue(val)); }
	void AddColumn(const std::string name, const char* val)  { AddColumn(name, new MdsValue(val)); }

	// Act a bit like a container, but not all the way
	typedef std::vector<col_t>::iterator iterator;
	typedef std::vector<col_t>::const_iterator const_iterator;

	iterator begin() { return _entity.begin(); }
	const_iterator begin() const { return _entity.begin(); }
	iterator end() { return _entity.end(); }
	const_iterator end() const { return _entity.end(); }
	size_t size() const { return _entity.size(); }

	// For XJsonBlob & EventHub publishing support
	// timeGrain should be an empty string for log events, should be ISO8601 duration string (e.g., "PT1M") for metric events.
	// Caller is responsible to make all conditions true for metric events.
	// That is, when a non-empty timeGrain is passed (for a metric event), the row should
	// contain "CounterName" and "Last" columns.
	std::string GetJsonRow(const std::string& timeGrain,
			const std::string& tenant, const std::string& role, const std::string& roleInstance) const;

	void SetSourceType(SourceType t) { _srctype = t; }
	SourceType GetSourceType() const { return _srctype; }

private:
	std::vector<col_t> _entity;
	MdsTime _timestamp;
	std::string _pkey;
	std::string _rkey;
	SchemaCache::IdType _schemaId;
	SourceType _srctype = SourceType::Ingested;

	void CopyAddColumn(const col_t& col) { _entity.push_back(std::make_pair(col.first, new MdsValue(*(col.second)))); }

	std::string GetJsonRowForLog(const std::string& resourceId) const;
	std::string GetJsonRowForMetric(const std::string& resourceId, const std::string& timeGrain,
			const std::string& tenant, const std::string& role, const std::string& roleInstance) const;
};

std::ostream& operator<<(std::ostream& os, const CanonicalEntity& ce);

#endif // _CANONICALENTITY_HH_

// vim: se sw=8 :
