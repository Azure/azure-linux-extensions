// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#include "mdsd_input_reflection.h"
#include "bond/core/bond_types.h"
#include <string>
#include <unordered_map>
#include <mutex>

namespace mdsdinput
{

    class SchemaCache
    {
    public:
        SchemaCache() = default;
        SchemaCache(const SchemaCache&) = delete;
        SchemaCache(SchemaCache&&) = delete;
        SchemaCache& operator=(const SchemaCache&) = delete;
        SchemaCache& operator=(SchemaCache&&) = delete;

        // Returns the schema id and a flag indicating if the schema was new.
        std::pair<uint64_t, bool> AddSchema(const std::shared_ptr<SchemaDef>& schema);

        // Add a schema using supplied id.
        // Returns false if the id is already in use and the cached schema doesn't match the provided schema.
        bool AddSchemaWithId(const std::shared_ptr<SchemaDef>& schema, uint64_t id);

        // Return the schema. Throws an exception if not found.
        std::shared_ptr<SchemaDef> GetSchema(uint64_t id);

        // Return the bond schema. Throws an exception if not found.
        boost::shared_ptr<bond::SchemaDef> GetBondSchema(uint64_t id);

        // Return the schema key. Throws an exception if not found.
        std::string GetSchemaKey(uint64_t id);
    protected:
        std::string schemaKey(const std::shared_ptr<SchemaDef>& schema);

        std::mutex _lock;
        uint64_t _next_id;
        std::unordered_map<std::string, uint64_t> _schema_ids;
        std::unordered_map<uint64_t, std::string> _schema_keys;
        std::unordered_map<uint64_t, std::shared_ptr<SchemaDef>> _schemas;
        std::unordered_map<uint64_t, boost::shared_ptr<bond::SchemaDef>> _bond_schemas;
    };

}
