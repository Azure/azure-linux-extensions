// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _BATCH_HH_
#define _BATCH_HH_

#define MAX_BATCH_SIZE 100

#include <utility>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <ctime>
#include <iostream>
#include "MdsTime.hh"
#include "MdsEntityName.hh"

class MdsdConfig;
class MdsValue;
class Credentials;
class CanonicalEntity;
class IMdsSink;

class Batch
{
	friend std::ostream& operator<<(std::ostream& os, const Batch& batch);

public:
	/// <summary>Force all batched entities into MDS and leave the batch empty</summary>
	void Flush();

	/// <summary>Add a row to the batch. May trigger a flush which may or may not flush this row.</summary>
	/// <param name="row">The row to be added to the batch. Must be complete (includes all columns). Contents
	/// are copied elsewhere by the sink; caller can reuse the object if desired.</param>
	/// <param name="pkey">The PartitionKey for the row.</param>
	/// <param name="qibase">The QueryInterval to which this row is associated.</param>
	void AddRow(const CanonicalEntity &row);

	/// <summary>Add a row to a batch of entries destined for some SchemasTable</summary>
	void AddSchemaRow(const MdsEntityName &target, const std::string &hash, const std::string &schema);

	// <summary>True if the batch might have rows from a prior query interval</summary>
	bool HasStaleData() const; // { return (_lastAction < (_batchQIBase + _interval)); }

	~Batch();

private:
	Batch(MdsdConfig* config, const MdsEntityName &target, const Credentials* creds, int interval);
	Batch();				// No void constructor
	Batch(const Batch&);			// No copy constructor
	Batch& operator=(const Batch&);		// Can't assign

	/// <summary>Update the _lastAction time.</summary>
	void MarkTime() { _lastAction.Touch(); _dirty = true; }
	void MarkFlushed() { _lastAction = MdsTime::Max(); _dirty = false; }
	bool IsDirty() const { return _dirty; }
	bool IsClean() const { return (! _dirty); }

	MdsdConfig *_config;
	MdsTime _lastAction;			// Used to find lingering batches
	MdsTime _batchQIBase;			// The Query Interval base timestamp for the current batch
	int _interval;				// The width of the interval (in seconds)

	IMdsSink* _sink;

	std::recursive_mutex _mutex;

	bool _dirty;				// "Dirty" bit; set if any AddRow was called since last flush

	friend class BatchSet;
};

std::ostream& operator<<(std::ostream& os, const Batch& batch);

class BatchSet
{
public:
	BatchSet(MdsdConfig* c) : _config(c) {}
	~BatchSet();

	// <summary>Get pointer to a Batch object for this table</summary>
	// <param name=target>The metadata for the destination for the batch's data</param>
	// <param name=interval>The "query interval" for the batch, i.e. how often it gets flushed</param>
	Batch* GetBatch(const MdsEntityName &target, int interval);

	void Flush();
	void FlushIfStale();

private:
	using key_t = std::pair<std::string, const Credentials*>;

	BatchSet(const BatchSet&);		// No copy constructor
	BatchSet& operator=(const BatchSet&);	// No copying

	std::map<key_t, Batch*> _map;

	MdsdConfig* _config;
	std::mutex _mutex;			// Just covers the BatchSet object, not any of the Batches in the set
};

#endif // _BATCH_HH_

// vim: se sw=8 :
