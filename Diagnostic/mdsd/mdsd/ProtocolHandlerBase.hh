// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_HANDLER_BASE_HH
#define _PROTOCOL_HANDLER_BASE_HH

#include "SchemaCache.hh"
#include <mutex>
#include <unordered_map>

/*
 * This class exists to eliminate duplicate code shared by the ProtocolHandler classes.
 *
 * The subclasses (e.g. ProtocolHandlerBond) are not, nor intended to be, thread safe.
 * The ProtocolListener classes allocate a separate instance per connection where each connection
 * has a separate thread.
 */
class ProtocolHandlerBase
{
protected:
    virtual ~ProtocolHandlerBase() = default;

    std::unordered_map<uint64_t, SchemaCache::IdType> _id_map;

    static SchemaCache::IdType schema_id_for_key(const std::string& key);
    static std::mutex _static_lock;
    static std::unordered_map<std::string, SchemaCache::IdType> _key_id_map;
};


#endif //_PROTOCOL_HANDLER_BASE_HH
