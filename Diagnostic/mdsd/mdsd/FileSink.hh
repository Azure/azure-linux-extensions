// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _FILESINK_HH_
#define _FILESINK_HH_

#include "IMdsSink.hh"
#include <map>
#include <functional>
#include <string>
#include <mutex>
#include <fstream>
#include <vector>
#include <exception>
#include "MdsTime.hh"
#include "MdsEntityName.hh"
#include "CanonicalEntity.hh"

class FileSink : public IMdsSink
{
public:
	FileSink(const std::string&);	// Private constructor; must be called with _mapMutex locked
	virtual ~FileSink();

	virtual bool IsFile() const { return true; }
	virtual void AddRow(const CanonicalEntity&, const MdsTime&);
	virtual void Flush();

private:
	const std::string _name;
	std::string _path;

	std::ofstream _file;

	std::mutex _mutex;

	std::vector<std::string> items;

	void Open();
	void Close() { try { _file.close(); } catch (const std::exception&) { } }
};

#endif // _FILESINK_HH_

// vim: se sw=8 :
