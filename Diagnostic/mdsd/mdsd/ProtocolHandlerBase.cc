// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolHandlerBase.hh"

std::mutex ProtocolHandlerBase::_static_lock;
std::unordered_map<std::string, SchemaCache::IdType> ProtocolHandlerBase::_key_id_map;


SchemaCache::IdType
ProtocolHandlerBase::schema_id_for_key(const std::string& key)
{
    std::lock_guard<std::mutex> lock(_static_lock);

    auto it = _key_id_map.find(key);

    if (it != _key_id_map.end()) {
        return it->second;
    } else {
        auto id = SchemaCache::Get().GetId();
        _key_id_map.insert(std::make_pair(key, id));
        return id;
    }
}
