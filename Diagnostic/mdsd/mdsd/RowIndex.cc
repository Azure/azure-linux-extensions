// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "RowIndex.hh"
#include <ctime>
#include <climits>
#include <mutex>

thread_local unsigned long long RowIndex::_index = ULLONG_MAX;
unsigned long long RowIndex::_baseValue = 0;
std::mutex RowIndex::_mutex;

unsigned long long
RowIndex::Get()
{
	if (_index == ULLONG_MAX) {
		unsigned long long now = (((unsigned long long) time(0)) & 0xfffff) << 32;
		std::lock_guard<std::mutex> lock(_mutex);
		_index = _baseValue + now;
		_baseValue += 1ULL << 54;
	}

	return _index++;
}
