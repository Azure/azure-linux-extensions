// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "StoreType.hh"

#include <map>
#include <string>
#include "Utility.hh"
extern "C" {
#include <limits.h>
}

namespace StoreType {

// Names should be all lower case, since from_string canonicalizes to lower case
// before searching the map
static std::map<std::string, StoreType::Type> typeMap {
	{ "local", StoreType::Type::Local },
	{ "xtable", StoreType::Type::XTable },
	{ "central", StoreType::Type::XTable },
	{ "jsonblob", StoreType::Type::XJsonBlob },
	{ "centraljson", StoreType::Type::XJsonBlob },  // For parity with WAD...
	{ "file", StoreType::Type::File }
};

static std::map<StoreType::Type, size_t> nameLengthLimit {
	{ StoreType::Type::None, 0 },
	{ StoreType::Type::XTable, 63 },
	{ StoreType::Type::XJsonBlob, PATH_MAX /* No explicit limit we've heard about this. */ },
	{ StoreType::Type::Local, 255 },
	{ StoreType::Type::File, PATH_MAX }
};

static std::map<StoreType::Type, bool> needsSchemaGeneration {
	{ StoreType::Type::None, false },
	{ StoreType::Type::XTable, true },
	{ StoreType::Type::XJsonBlob, false },
	{ StoreType::Type::Local, false },
	{ StoreType::Type::File, false }
};

Type
from_string(const std::string & n)
{
	const auto &iter = typeMap.find(MdsdUtil::to_lower(n));
	if (iter == typeMap.end()) {
		return None;
	} else {
		return iter->second;
	}
}

size_t
max_name_length(StoreType::Type t)
{
	const auto & iter = StoreType::nameLengthLimit.find(t);
	if (iter == StoreType::nameLengthLimit.end()) {
		return 0;
	} else {
		return iter->second;
	}
}

bool
DoSchemaGeneration(StoreType::Type storetype)
{
	const auto &iter = needsSchemaGeneration.find(storetype);
	if (iter == needsSchemaGeneration.end()) {
		throw std::domain_error("Don't know if schema generation is needed for StoreType " + std::to_string(storetype));
	}
	
	return iter->second;
}

bool
DoAddIdentityColumns(StoreType::Type storetype)
{
	return (storetype != StoreType::Local);
}

};

// vim: se sw=8 :
