// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _SCHEMACACHE_HH_
#define _SCHEMACACHE_HH_
#pragma once

#include <mutex>
#include <memory>
#include <atomic>
#include <map>
#include <string>
#include <cstdint>
#include <iostream>
#include "Crypto.hh"

/*
	The notion of "schema" is tied to the CanonicalEvent. Each row in an MDS destination
	(table, Bond blob, etc.) can have its own schema.
	The generator of a CanonicalEvent (JSON, OMI, query engine) can "know" the schema.
	PipeStages that alter the CE can likewise "know" the altered schema.

	So...

	o Tag the CE (at instantiation) with its schema id as "known" by the source/generator.
	o PipeStage augmentors should map from input schema id to output schema id (the new,
	  altered schema produced by the augmenting stage). These are general-purpose augmentor (e.g.
	  "Add identity columns") and should literally keep a map of <inputID, outputID>.
	o A unique augmenter (e.g. a configured query) should gets its own schema ID when the config
	  is processed. If the augmentor performs an identity transformation, it should pass along
	  the input schema ID(s). If it does its own projection, it should have its own (new) ID.
*/

class SchemaCache
{
public:
	/////////////  Types    //////////

	// The id type
	using IdType = unsigned long long;

	// The actual data kept in the cache.
	// The result of the Schema() method shares lifetime with the Info object; if you want it to live longer
	// you'll need to copy it. Same for the MD5Hash returned by the Hash() method.
	class Info {
	public:
		Info(SchemaCache::IdType id, std::string schema);

		SchemaCache::IdType	Id() const { return _id; }
		const std::string&	Schema() const { return _schema; }
		const Crypto::MD5Hash &	Hash() const { return _md5; }

	private:
		SchemaCache::IdType	_id;
		std::string		_schema;
		Crypto::MD5Hash		_md5;
	};

	// The kinds of schema we can store
	enum Kind { Unknown, XTable, Bond };

	// The value type is a shared pointer to the Info object.
	// When we return the shared_ptr to clients, the ref count on the actual object is
	// managed for us. When the last shared_ptr is deleted, the underlying object is cleaned up.
	using CachedType = std::shared_ptr<SchemaCache::Info>;

	/////////////  Methods  //////////
	
	// Return the singleton instance of the SchemaCache
	static SchemaCache& Get();

	// Allocate a new schema ID and return it. Using an atomic_long, so no locking needed.
	SchemaCache::IdType GetId() noexcept { return _nextId++; }

	// Check to see if a schema of a given kind has been cached for a given ID
	bool IsCached(SchemaCache::IdType id, SchemaCache::Kind kind) noexcept;

	// Return the cached schema of that kind for that id. Throws if none is cached.
	CachedType Find(SchemaCache::IdType id, SchemaCache::Kind kind);

	// Remove a cached schema. Silent if nothing is cached for the id/kind
	void Evict(SchemaCache::IdType id, SchemaCache::Kind kind) noexcept;

	// Insert a schema. Discard the currently cached schema, if any.
	// The schema is moved into the Info object, if possible.
	void Insert(SchemaCache::IdType id, SchemaCache::Kind kind, std::string schema);

#ifdef ENABLE_TESTING
	friend void TEST__SchemaCache_Reset();
	friend std::map<SchemaCache::IdType, SchemaCache::CachedType>& TEST__SchemaCache_Select(Kind kind);
#endif

	//////////  Stream IO  //////////
	friend std::ostream& operator<<(std::ostream&, Kind);

private:
	// Default constructor is private and used by the static accessor. Neither copy nor move or assignment
	// are allowed.
	SchemaCache() : _nextId(1) {}
	SchemaCache(const SchemaCache &) = delete;
	SchemaCache& operator=(const SchemaCache &) = delete;

	static SchemaCache *	_singleton;	// Points to the singleton instance of this class
	// As a static, the linker will ensure this is all zeroes, the correct bit pattern for nullptr

	static std::mutex	_mutex;		// Protects access to the cache

	std::atomic_ullong	_nextId;	// Next schema ID to use

	// We only have two kinds of schemas, so make each schema its own map and provide a simple
	// method to get a reference to the map for any particular kind. This is moderately scalable;
	// the Select method is a fast switch() on the Kind. At a certain point, it may become
	// smarter to change to a single map whose key is pair<Kind, IdType>. Eliminate Select() and
	// simply build the right key wherever it's used.
	std::map<SchemaCache::IdType, SchemaCache::CachedType> _BondCache;
	std::map<SchemaCache::IdType, SchemaCache::CachedType> _XTableCache;

	// Return a reference to the map which caches the desired schema type
	std::map<SchemaCache::IdType, SchemaCache::CachedType>& Select(Kind kind);

};

#ifdef ENABLE_TESTING
void TEST__SchemaCache_Reset();
std::map<SchemaCache::IdType, SchemaCache::CachedType>& TEST__SchemaCache_Select(SchemaCache::Kind kind);
#endif // ENABLE_TESTING

#endif // _SCHEMACACHE_HH_

// vim: se ai sw=8 :
