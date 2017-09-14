// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsdInputSchemaCache.h"
#include "bond/core/apply.h"
#include "bond/core/runtime_schema.h"
#include "bond/core/schema.h"

#include "stdio.h"

namespace mdsdinput
{

    std::pair<uint64_t, bool> SchemaCache::AddSchema(const std::shared_ptr<SchemaDef>& schema)
    {
        auto key = schemaKey(schema);

        std::lock_guard<std::mutex> lock(_lock);

        auto sk = _schema_ids.find(key);
        if (sk != _schema_ids.end())
        {
            return std::make_pair((*sk).second, false);
        }

        uint64_t id = _next_id++;
        _schemas.insert(std::make_pair(id, schema));
        _schema_ids.insert(std::make_pair(key, id));
        _schema_keys.insert(std::make_pair(id, key));

        return std::make_pair(id, true);
    }

    bool SchemaCache::AddSchemaWithId(const std::shared_ptr<SchemaDef>& schema, uint64_t id)
    {
        auto key = schemaKey(schema);

        std::lock_guard<std::mutex> lock(_lock);

        auto it = _schema_keys.find(id);

        if (it != _schema_keys.end())
        {
            if (it->second == key)
            {
                return true;
            } else {
                return false;
            }
        }

        _schemas.insert(std::make_pair(id, schema));
        _schema_ids.insert(std::make_pair(key, id));
        _schema_keys.insert(std::make_pair(id, key));

        return true;
    }

    std::shared_ptr<SchemaDef> SchemaCache::GetSchema(uint64_t id)
    {
        std::lock_guard<std::mutex> lock(_lock);

        return _schemas.at(id);
    }

    std::string SchemaCache::GetSchemaKey(uint64_t id)
    {
        std::lock_guard<std::mutex> lock(_lock);

        return _schema_keys.at(id);
    }

    std::string SchemaCache::schemaKey(const std::shared_ptr<SchemaDef>& schema)
    {
        std::string key;

        if (!schema->timestampFieldIdx.empty()) {
            key.append(std::to_string(*(schema->timestampFieldIdx)));
        }
        for (const auto & it : schema->fields) {
            key.append(ToString(it.fieldType));
            key.append(it.name);
        }

        return key;
    }

    static boost::shared_ptr<bond::SchemaDef> makeBondSchema(const std::shared_ptr<SchemaDef>& s)
    {
        auto bs = boost::make_shared <bond::SchemaDef>();
        bond::StructDef st;
        bool _time_added = false;
        uint16_t _time_id = 1; // Time is always the second struct and thus has ID 1.
        uint16_t id = 0;
        for (const auto & it : s->fields)
        {
            bond::FieldDef f;
            f.id = id;
            id++;
            f.metadata.name = it.name;
            switch (it.fieldType)
            {
            case FT_INVALID:
                throw std::runtime_error("FT_INVALID encountered!");
            case FT_BOOL:
                f.type.id = bond::BT_BOOL;
                break;
            case FT_INT32:
                f.type.id = bond::BT_INT32;
                break;
            case FT_INT64:
                f.type.id = bond::BT_INT64;
                break;
            case FT_DOUBLE:
                f.type.id = bond::BT_DOUBLE;
                break;
            case FT_TIME:
                f.type.id = bond::get_type_id<Time>::value;
                f.type.struct_def = _time_id;
                f.type.bonded_type = bond::is_bonded<Time>::value;
                _time_added = true;
                break;
            case FT_STRING:
                f.type.id = bond::BT_STRING;
                break;
            }
            st.fields.push_back(f);
        }
        bs->structs.push_back(st);
        if (_time_added)
        {
            bond::detail::SchemaCache<Time, void>::AppendStructDef(bs.get());
        }

        bs->root.id = bond::BT_STRUCT;
        bs->root.bonded_type = false;
        bs->root.struct_def = 0;

        return bs;
    }

    boost::shared_ptr<bond::SchemaDef> SchemaCache::GetBondSchema(uint64_t id)
    {
        auto it = _bond_schemas.find(id);
        if (it == _bond_schemas.end())
        {
            auto s = _schemas.at(id);
            auto bs = makeBondSchema(s);
            _bond_schemas.insert(std::make_pair(id, bs));
            return bs;
        }
        else
        {
            return it->second;
        }
    }

}
