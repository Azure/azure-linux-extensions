// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsSchemaMetadata.hh"
#include "Crypto.hh"
#include "IdentityColumns.hh"
#include "TableSchema.hh"
#include "Trace.hh"
#include "MdsEntityName.hh"
#include "CanonicalEntity.hh"
#include <algorithm>
#include <map>
#include <string>
#include <vector>
#include <unordered_set>

using std::string;
using std::vector;

std::map<string, MdsSchemaMetadata*> MdsSchemaMetadata::_cache;
std::mutex MdsSchemaMetadata::_mutex;

#define STRINGPAIR(a,b) std::make_pair(string(a),string(b))
typedef std::pair<std::string, std::string> coldata_t;

const std::unordered_set<std::string> MdsSchemaMetadata::MetadataColumns
        { "TIMESTAMP", "PreciseTimeStamp", "PartitionKey", "RowKey", "N", "RowIndex" };

// Given a set of destination metadata and a CanonicalEntity, build the metadata MDS needs
// to interpret the destination object (table, Bond blob, etc.)
MdsSchemaMetadata*
MdsSchemaMetadata::GetOrMake(const MdsEntityName &target, const CanonicalEntity* ce)
{
	if (!ce) {
		return nullptr;
	}

        vector<coldata_t> unsortedSchema;
	unsortedSchema.reserve(ce->size() + 6);

        // First, the timestamps...
	unsortedSchema.push_back(STRINGPAIR("TIMESTAMP", "mt:utc"));
	unsortedSchema.push_back(STRINGPAIR("PreciseTimeStamp", "mt:utc"));

	// Next, the data and identity columns (the identity columns are expected to have
	// already been added by this point). Ignore any of the "special" columns.
	for (const auto & col : *ce) {
		if (! MetadataColumns.count(col.first)) {
			unsortedSchema.push_back(STRINGPAIR(col.first, col.second->TypeToString()));
		}
	}

	// XTable targets get some extra metadata
	if (target.GetStoreType() == StoreType::Type::XTable) {
		unsortedSchema.push_back(STRINGPAIR("PartitionKey", "mt:wstr"));
		unsortedSchema.push_back(STRINGPAIR("RowKey", "mt:wstr"));
		unsortedSchema.push_back(STRINGPAIR("N", "mt:wstr"));
		unsortedSchema.push_back(STRINGPAIR("RowIndex", "mt:wstr"));
	}

	return GetOrMake(unsortedSchema);
}


// Given a vector of <name,type> pairs,
// build the MDS table metadata (XML-format schema and MD5 hash of canonicalized schema).
MdsSchemaMetadata*
MdsSchemaMetadata::GetOrMake(vector<coldata_t>& schema)
{
        string elements;
        for (auto it = schema.cbegin(); it != schema.cend(); ++it) {
                elements += "<Column name=\"" + it->first + "\" type=\"" + it->second + "\"></Column>";
        }

        std::sort(schema.begin(), schema.end(),
                [](coldata_t left, coldata_t right) -> bool { return (left.first.compare(right.first) < 0); } );

        int columnCount = schema.size();
        string schemaForMD5;

        for (int i = 0; i < columnCount; ++i) {
                schemaForMD5 += schema[i].first + "," + schema[i].second;
                if (i < (columnCount-1)) {
                        schemaForMD5 += ",";
                }
        }

        string md5 = Crypto::MD5HashString(schemaForMD5).to_string();

	std::lock_guard<std::mutex> lock(_mutex);	// Take lock on _cache; lock is released at function return

	auto it = _cache.find(schemaForMD5);
	if (it != _cache.end()) {
		return it->second;
	}

	// Lock contention is rare, hits are common, and this string can
	// get moderately large. Deferring assembly until needed should save time in the long run.

        string xmldata = "<MdsConfig><Schemas><Schema name=\"Schema_" + md5  + "\">";
        xmldata += elements;
        xmldata += "</Schema></Schemas></MdsConfig>";

	_cache[schemaForMD5] = new MdsSchemaMetadata(move(xmldata), move(md5), columnCount);

	return _cache[schemaForMD5];		// Be sure to return the address of the object in the cache
}

#ifdef DOING_MEMCHECK
// Remove everything from the cache.
void
MdsSchemaMetadata::ClearCache()
{
	Trace trace(Trace::ConfigLoad, "MdsSchemaMetadata::ClearCache");

	std::lock_guard<std::mutex> lock(_mutex);

	size_t count = 0;
	for (auto entry : _cache) {
		delete entry.second;
		count++;
	}
	_cache.clear();
	trace.NOTE("Deleted " + std::to_string(count) + " MdsSchemaMetadata objects from cache");
}
#endif

// vim: se sw=8 :
