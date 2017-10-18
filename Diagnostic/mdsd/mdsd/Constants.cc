// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Constants.hh"
#include <fstream>
#include <string>

#define DEFINE_STRING(name, value) const std::string name { value }; const std::wstring name ## W { L ## value };

uint64_t Constants::_UniqueId { 0 };

namespace Constants {

const std::string TIMESTAMP { "TIMESTAMP" };
const std::string PreciseTimeStamp { "PreciseTimeStamp" };

namespace Compression {
	const std::string lz4hc { "lz4hc" };
} // namespace Compression

namespace EventCategory {
	const std::string Counter { "counter" };
	const std::string Trace { "trace" };
} // namespace EventCategory

namespace AzurePropertyNames {
	DEFINE_STRING(Namespace, "namespace")
	DEFINE_STRING(EventName, "eventname")
	DEFINE_STRING(EventVersion, "eventversion")
	DEFINE_STRING(EventCategory, "eventcategory")
	DEFINE_STRING(BlobVersion, "version")
	DEFINE_STRING(BlobFormat, "format")
	DEFINE_STRING(DataSize, "datasizeinbytes")
	DEFINE_STRING(BlobSize, "blobsizeinbytes")
	DEFINE_STRING(MonAgentVersion, "monagentversion")
	DEFINE_STRING(CompressionType, "compressiontype")
	DEFINE_STRING(MinLevel, "minlevel")
	DEFINE_STRING(AccountMoniker, "accountmoniker")
	DEFINE_STRING(Endpoint, "endpoint")
	DEFINE_STRING(OnbehalfFields, "onbehalffields")
	DEFINE_STRING(OnbehalfServiceId, "onbehalfid")
	DEFINE_STRING(OnbehalfAnnotations, "onbehalfannotations")
} // namespace AzurePropertyNames


uint64_t
UniqueId()
{
	static std::string digits { "0123456789ABCDEFabcdef" };

	if (!Constants::_UniqueId) {
		std::ifstream bootid("/proc/sys/kernel/random/boot_id", std::ifstream::in);
		if (bootid.is_open()) {
			uint64_t id = 0;
			int nybbles = 16;
			while (nybbles && bootid.good()) {
				char c = bootid.get();
				size_t pos = digits.find(c);
				if (pos != std::string::npos) {
					if (pos > 15) {
						pos -= 6;
					}
					id <<= 4;
					id += pos;
					nybbles--;
				}
			}
			if (id == 0) {
				id = 1;		// Backstop in case something got weird
			}
			Constants::_UniqueId = id;
		} else {
			Constants::_UniqueId = 1;		// Backstop in case something got weird
		}
	}

	return Constants::_UniqueId;
}

} // namespace Constants

// vim: se sw=8 :
