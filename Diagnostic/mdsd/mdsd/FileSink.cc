// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "FileSink.hh"

#include <iterator>
#include <sstream>

#include "CanonicalEntity.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"
#include "RowIndex.hh"
#include "Trace.hh"
#include "MdsdMetrics.hh"
#include "StoreType.hh"
#include "Logger.hh"

// FileSink uses the name of the sink as the pathname. If the path isn't absolute, we make it
// relative to /tmp.
//
// By design, each invocation of this constructor creates an independent
// instance with its own ostream. They're all opened in append mode, which should keep simultaneous
// writes from being interleaved. If writes are large enough that they become interleaved, this
// design will need to be revisited. Perhaps Batches should hold reference-counted pointers to their
// sinks, so that the destruction of the last batch instance pointing to a sink causes the sink to
// be destroyed. Add to that a map from filename to a weak pointer to the filesink; when the FileSink
// destructor is called (when the last strong refcounted pointer goes away), the destructor removes the weak
// pointer from the map.
//
FileSink::FileSink(const std::string &name)
  : IMdsSink(StoreType::Type::File), _name(name)
{
	Trace trace(Trace::Local, "FileSink::Constructor");

	// Construct _path based on default directory
	if (name[0] != '/') {
		_path = "/tmp/";	// Make a relative path into an absolute path
	}
	_path += name;

	// Do a quick sanity check to make sure the file can be opened. Allow any exception
	// from Open() to propagate upwards.
	Open();
	Close();
}

// When destroying, remove from the global list of file sinks. No need to close the file; the 
// destructor for ostream is defined as closing the file.
FileSink::~FileSink()
{
	Trace trace(Trace::Local, "FileSink::Destructor");
}

void
FileSink::Open()
{
	if (! _file.is_open()) {
		_file.open(_path, std::ofstream::app);	// Open for write in append mode
		if (!_file) {
			std::system_error e(errno, std::system_category(), "Failed to open " + _path + " for append");
			Logger::LogError("Error: " + e.code().message() + " - " + e.what());
			throw e;
		}
	}
}

// Write the row, in readable form, to the output file. Add a timestamp. Don't bother with
// async disk file writes; the primary goal of the FileSink is testability, so stability and certainty
// is more important than absolute performance.
void
FileSink::AddRow(const CanonicalEntity &row, const MdsTime &)
{
	std::lock_guard<std::mutex> lock(_mutex);
#if BUFFER_ALL_DATA
	std::ostringstream msg;
	msg << MdsTime::Now() << "\t" << row << "\n";
	items.push_back(std::move(msg.str()));
#else
	try {
		Open();
		// If you emit std::endl, that does a flush, which isn't what we want.
		_file << MdsTime::Now() << "\t" << row << "\n";
	}
	catch (const std::exception&)
	{ }
#endif
}

void
FileSink::Flush()
{
	Trace trace(Trace::Local, "FileSink::Flush");

	std::lock_guard<std::mutex> lock(_mutex);
#if BUFFER_ALL_DATA
	try {
		Open();
		for (const auto& item : items) {
			_file << item;
		}
	}
	catch (const std::exception&)
	{ }
	items.clear();
#endif
	Close();
}

// vim: se sw=8 :
