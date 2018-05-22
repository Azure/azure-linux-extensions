// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _PRIORITY_HH_
#define _PRIORITY_HH_

#include <string>
#include <ctime>

class Priority
{
public:
	Priority(const std::string & name);
	Priority() : _duration(300) {}
	~Priority() {}

	bool Set(const std::string & name);

	time_t Duration() const { return _duration; }

private:
	time_t _duration;
};

#endif // _PRIORITY_HH_

// vim: se sw=8 :
