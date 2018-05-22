// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _CONSTANTS_HH_
#define _CONSTANTS_HH_
#pragma once

#define DECLARE_STRING(name) extern const std::string name; extern const std::wstring name ## W;

#include <string>

namespace Constants
{
	extern const std::string TIMESTAMP;
	extern const std::string PreciseTimeStamp;
	enum class ETWlevel : unsigned char { LogAlways = 0, Critical = 1, Error = 2, Warning = 3, Information = 4, Verbose = 5 };

	static constexpr uint32_t MDS_blob_version { 1 };
	static constexpr uint32_t MDS_blob_format  { 2 };

	extern uint64_t _UniqueId;
	uint64_t UniqueId();

	namespace Compression {
		extern const std::string lz4hc;
	}

	namespace EventCategory {
		extern const std::string Counter;
		extern const std::string Trace;
	} // namespace EventCategory

	namespace AzurePropertyNames {
		DECLARE_STRING(Namespace)
		DECLARE_STRING(EventName)
		DECLARE_STRING(EventVersion)
		DECLARE_STRING(EventCategory)
		DECLARE_STRING(BlobVersion)
		DECLARE_STRING(BlobFormat)
		DECLARE_STRING(DataSize)
		DECLARE_STRING(BlobSize)
		DECLARE_STRING(MonAgentVersion)
		DECLARE_STRING(CompressionType)
		DECLARE_STRING(MinLevel)
		DECLARE_STRING(AccountMoniker)
		DECLARE_STRING(Endpoint)
		DECLARE_STRING(OnbehalfFields)
		DECLARE_STRING(OnbehalfServiceId)
		DECLARE_STRING(OnbehalfAnnotations)
	} // namespace AzurePropertyNames

};

#undef DECLARE_STRING

#endif // _CONSTANTS_HH_

// vim: se sw=8
