// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Priority.hh"

#include <map>
#include "Utility.hh"

static std::map<std::string, time_t> priorityMap {
	{ "high", 60 },
	{ "medium", 300 }, { "normal", 300 }, { "default", 300 },
	{ "low", 900 } };

Priority::Priority(const std::string & name)
{
	const auto &iter = priorityMap.find(MdsdUtil::to_lower(name));
	if (iter == priorityMap.end()) {
		_duration = priorityMap["default"];
	} else {
		_duration = iter->second;
	}
}

bool
Priority::Set(const std::string & name)
{
	const auto &iter = priorityMap.find(MdsdUtil::to_lower(name));
	if (iter == priorityMap.end()) {
		return false;
	}

	_duration = iter->second;
	return true;
}

// vim: se sw=8 :
