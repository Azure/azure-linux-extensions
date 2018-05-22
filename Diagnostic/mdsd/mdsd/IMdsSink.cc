// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "IMdsSink.hh"
#include "XTableSink.hh"
#include "LocalSink.hh"
#include "FileSink.hh"
#include "XJsonBlobSink.hh"
#include "Trace.hh"
#include "Logger.hh"

#include <map>
#include <string>

IMdsSink*
IMdsSink::CreateSink(MdsdConfig * config, const MdsEntityName &target, const Credentials* creds)
{
	Trace trace(Trace::ConfigLoad, "IMdsSink::CreateSink");

	switch (target.GetStoreType()) {

		case StoreType::XTable:
			return new XTableSink(config, target, creds);

		case StoreType::Local:
			return new LocalSink(target.Basename());

		case StoreType::File:
			return new FileSink(target.Basename());

		case StoreType::XJsonBlob:
		    return new XJsonBlobSink(config, target, creds);

		default:
			std::ostringstream msg;
			msg << "Attempt to create sink of unknown type for target " << target;
			Logger::LogError(msg.str());
			trace.NOTE(msg.str());
			throw std::logic_error(msg.str());
	}
}

// vim: se sw=8 :
