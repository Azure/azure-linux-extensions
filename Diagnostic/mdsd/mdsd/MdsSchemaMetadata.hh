// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _MDSSCHEMAMETADATA_HH_
#define _MDSSCHEMAMETADATA_HH_

#include <string>
#include <utility>
#include <vector>
#include <map>
#include <mutex>
#include <unordered_set>
#include "Crypto.hh"
#include "IdentityColumns.hh"
#include "MdsEntityName.hh"

class TableSchema;
class CanonicalEntity;

class MdsSchemaMetadata
{
public:
    typedef std::pair<std::string, std::string> coldata_t;

    static const std::unordered_set<std::string> MetadataColumns;

	// Check cache for schema; if it exists, return pointer. Otherwise, create it, add it to cache, and return pointer.
	static MdsSchemaMetadata* GetOrMake(const MdsEntityName &target, const CanonicalEntity* ce);

	const std::string& GetXML() const { return _xmldata; }
	const std::string& GetMD5() const { return _md5; }
	size_t GetSize() const { return _size; }

#ifdef DOING_MEMCHECK
	static void ClearCache();
#endif

private:
	const std::string _xmldata;	// The MDS SchemasTable "Schema" column representation
	const std::string _md5;	// The MD5 checksum of the canonicalized schema
	const size_t _size;	// The number of columns, including identity columns and everything else

	MdsSchemaMetadata(std::string&& x, std::string&& m, size_t s) : _xmldata(x), _md5(m), _size(s) {}
	MdsSchemaMetadata() = delete;		// No default constructor

	static MdsSchemaMetadata* GetOrMake(std::vector<coldata_t>&);

	// Maps from canonical name/type list to the object
	static std::map<std::string, MdsSchemaMetadata*> _cache;
	static std::mutex _mutex;	// Ensures access to the cache is serialized
};

#endif // _MDSSCHEMAMETADATA_HH_
