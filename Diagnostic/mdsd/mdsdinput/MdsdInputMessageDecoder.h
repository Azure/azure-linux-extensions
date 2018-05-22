// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#include "mdsd_input_reflection.h"
#include <string>
#include "MdsdInputSchemaCache.h"
#include "bond/core/bond.h"
#include "bond/stream/input_buffer.h"
#include "bond/protocol/simple_binary.h"
#include <cstdio>
#include <iostream>

namespace mdsdinput
{

    class MessageDecoder
    {
    public:
        MessageDecoder()
            : _schema_cache(std::make_shared<SchemaCache>())
        {}

        MessageDecoder(std::shared_ptr<SchemaCache>& schemaCache)
            : _schema_cache(schemaCache)
        {}

        template<typename FieldReceiver>
        ResponseCode Decode(const Message& msg, FieldReceiver& receiver)
        {
            std::shared_ptr<SchemaDef> schema;
            if (!msg.schema.empty())
            {
                schema = std::make_shared<SchemaDef>(msg.schema.value());
                if (!_schema_cache->AddSchemaWithId(schema, msg.schemaId))
                {
                    return ACK_DUPLICATE_SCHEMA_ID;
                }
            }
            else
            {
                try
                {
                    schema = _schema_cache->GetSchema(msg.schemaId);
                }
                catch (std::out_of_range ex)
                {
                    return ACK_UNKNOWN_SCHEMA_ID;
                }
            }

            bond::SimpleBinaryReader<bond::InputBuffer> reader(msg.data);

            int32_t idx = 0;
            for (auto it = schema->fields.begin(); it != schema->fields.end(); ++it, ++idx)
            {
                try
                {
                    switch (it->fieldType)
                    {
                    case FT_INVALID:
                        return ACK_DECODE_ERROR;
                    case FT_BOOL:
                        {
                            bool b;
                            reader.Read(b);
                            receiver.BoolField(it->name, b);
                            break;
                        }
                    case FT_INT32:
                        {
                            int32_t i;
                            reader.Read(i);
                            receiver.Int32Field(it->name, i);
                            break;
                        }
                    case FT_INT64:
                        {
                            int64_t i;
                            reader.Read(i);
                            receiver.Int64Field(it->name, i);
                            break;
                        }
                    case FT_DOUBLE:
                        {
                            double d;
                            reader.Read(d);
                            receiver.DoubleField(it->name, d);
                            break;
                        }
                    case FT_TIME:
                        {
                            Time t;
                            reader.Read(t.sec);
                            reader.Read(t.nsec);
                            receiver.TimeField(it->name, t, (!schema->timestampFieldIdx.empty() && *(schema->timestampFieldIdx) == static_cast<uint32_t>(idx)));
                            break;
                        }
                    case FT_STRING:
                        {
                            std::string str;
                            reader.Read(str);
                            receiver.StringField(it->name, str);
                            break;
                        }
                    }
                }
                catch (bond::StreamException& ex)
                {
                    return ACK_DECODE_ERROR;
                }
            }

            return ACK_SUCCESS;
        }

        std::shared_ptr<SchemaDef> GetSchema(uint64_t id)
        {
            return _schema_cache->GetSchema(id);
        }

        std::string GetSchemaKey(uint64_t id)
        {
            return _schema_cache->GetSchemaKey(id);
        }

    protected:
        std::shared_ptr<SchemaCache> _schema_cache;
    };
}