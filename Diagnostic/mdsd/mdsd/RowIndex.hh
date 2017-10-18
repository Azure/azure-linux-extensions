// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _ROWINDEX_HH_
#define _ROWINDEX_HH_

#include <mutex>

class RowIndex
{
public:
	static unsigned long long Get();
private:
	static thread_local unsigned long long _index;
	static unsigned long long _baseValue;
	static std::mutex _mutex;

	RowIndex();
};

#endif //_ROWINDEX_HH_

// vim: se sw=8 :
