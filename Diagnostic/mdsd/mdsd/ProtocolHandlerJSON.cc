// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>
#include "ProtocolHandlerJSON.hh"

#include "Logger.hh"
#include "MdsValue.hh"
#include "CanonicalEntity.hh"
#include "Trace.hh"
#include "LocalSink.hh"
#include "Utility.hh"

extern "C" {
#include <unistd.h>
}

ProtocolHandlerJSON::~ProtocolHandlerJSON()
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::Destructor");
    close(_fd);
    Logger::LogInfo(std::string("ProtocolHandlerJSON: Connection on ") + std::to_string(_fd) +  " closed");
}

void ProtocolHandlerJSON::Run()
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::Run");
    msg_data_t msg_data;
    while(true)
    {
        try
        {
            mdsdinput::Ack ack;

            // Read message
            size_t msg_size = readMsgSize();
            readMsgData(msg_data, msg_size);

            // Process message
            ack = handleMsg(msg_data);

            // Ack message
            writeAck(ack.msgId, ack.code);
        }
        catch (mdsdinput::eof_exception)
        {
            Logger::LogInfo(std::string("ProtocolHandlerJSON: EOF on ") + std::to_string(_fd));
            return;
        }
        catch (mdsdinput::msg_too_large_error)
        {
            Logger::LogWarn(std::string("ProtocolHandlerJSON: Received oversized message on ") + std::to_string(_fd));
            return;
        }
        catch (std::exception& ex)
        {
            Logger::LogError(std::string("ProtocolHandlerJSON: Unexpected exception while processing messages on ") + std::to_string(_fd) + ": " + ex.what());
            return;
        }
    }
}

size_t ProtocolHandlerJSON::readMsgSize()
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::readMsgSize");
    char sbuf[8];
    size_t sidx = 0;

    do {
        ssize_t n = read(_fd, &sbuf[sidx], 1);
        if (n < 0)
        {
            if (errno != EINTR)
            {
                throw std::system_error(errno, std::system_category());
            }
        }
        else if (n == 0)
        {
            throw mdsdinput::eof_exception();
        }
        else
        {
            if (sbuf[sidx] == '\n')
            {
                break;
            }
            sidx++;
        }
    } while (sidx < sizeof(sbuf));

    if (sidx == sizeof(sbuf))
    {
        throw mdsdinput::msg_too_large_error("ProtocolHandlerJSON: Message size string is too long");
    }

    sbuf[sidx] = 0;

    size_t size = std::stoul(sbuf);
    if (size == 0 || size > MAX_MSG_DATA_SIZE)
    {
        throw std::runtime_error("Invalid message size");
    }

    return size;
}

void ProtocolHandlerJSON::readMsgData(msg_data_t& msg_data, size_t size)
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::readMsgData");

    char* ptr = &msg_data[0];
    size_t idx = 0;
    do {
        ssize_t n = read(_fd, ptr, size - idx);
        if (n < 0)
        {
            if (errno != EINTR)
            {
                throw std::system_error(errno, std::system_category());
            }
        }
        else if (n == 0)
        {
            throw mdsdinput::eof_exception();
        }
        else
        {
            idx += n;
            ptr += n;
        }
    } while (idx < size);
    msg_data[size] = 0;
}

void ProtocolHandlerJSON::writeAck(uint64_t msgId, mdsdinput::ResponseCode rcode)
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::writeAck");

    std::ostringstream out;
    out << msgId << ":" << rcode << std::endl;
    auto str = out.str();
    ssize_t n = write(_fd, str.c_str(), str.size());
    if (n < 0)
    {
        throw std::system_error(errno, std::system_category());
    }
    else if (n < static_cast<ssize_t>(str.size()))
    {
        throw mdsdinput::eof_exception();
    }
}

mdsdinput::Ack ProtocolHandlerJSON::decodeMsg(msg_data_t& msg_data, std::string& source, CanonicalEntity& ce)
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::decodeMsg");

    mdsdinput::Ack ack;
    rapidjson::Document d;
    d.ParseInsitu(&msg_data[0]);

    ack.code = mdsdinput::ACK_DECODE_ERROR;

    // Build/fetch schema
    if (!d.IsArray())
    {
        throw std::runtime_error("Invalid JSON document: Was not an array");
    }
    if (d.Size() != 5)
    {
        std::ostringstream msg;
        msg << "Invalid JSON document: Array size invalid: Expected 5, got " << d.Size();
        throw std::runtime_error(msg.str());
    }

    const rapidjson::Value& jsource = d[0];
    const rapidjson::Value& jmsgId = d[1];
    const rapidjson::Value& jschemaId = d[2];
    const rapidjson::Value& jschema = d[3];
    const rapidjson::Value& jmsgdata = d[4];

    if (!jsource.IsString())
    {
        throw std::runtime_error("Invalid JSON document: source (0) is not a String");
    }

    if (!jmsgId.IsNumber())
    {
        throw std::runtime_error("Invalid JSON document: msgId (1) is not a Number");
    }

    if (!jschemaId.IsNumber())
    {
        throw std::runtime_error("Invalid JSON document: schemaId (2) is not a Number");
    }

    if (!jmsgdata.IsArray())
    {
        throw std::runtime_error("Invalid JSON document: data (4) is not an Array");
    }

    if (!jschema.IsNull() && !jschema.IsArray())
    {
        throw std::runtime_error("Invalid JSON document: schema (3) is not an Array");
    }

    auto schema_id = jschemaId.GetUint64();

    std::shared_ptr<mdsdinput::SchemaDef> schema;
    if (!jschema.IsNull())
    {
        bool hasTimestampIndex = false;
        uint32_t timestampIndex;
        schema = std::make_shared<mdsdinput::SchemaDef>();

        for (rapidjson::Value::ConstValueIterator it = jschema.Begin(); it != jschema.End(); ++it)
        {
            if (it == jschema.Begin() && !it->IsArray())
            {
                // If the first element of the array is not an array, not null, and is an unsigned integer
                // then use it as the timestamp index.
                if (!it->IsNull() && it->IsUint())
                {
                    hasTimestampIndex = true;
                    timestampIndex = static_cast<uint32_t>(it->GetUint64());
                }
            }
            else
            {
                if (!it->IsArray() || it->Size() != 2)
                {
                    throw std::runtime_error("Invalid Schema");
                }
                const rapidjson::Value &name = (*it)[0];
                const rapidjson::Value &ft = (*it)[1];

                if (!name.IsString() || !ft.IsString())
                {
                    throw std::runtime_error("Invalid Schema");
                }
                mdsdinput::FieldDef fd;
                fd.name = name.GetString();
                if (!ToEnum(fd.fieldType, ft.GetString()))
                {
                    throw std::runtime_error("Invalid Schema");
                }
                schema->fields.push_back(fd);
            }
        }

        if (hasTimestampIndex)
        {
            if (timestampIndex < schema->fields.size())
            {
                schema->timestampFieldIdx.set(timestampIndex);
            }
        }

        if (!_schema_cache->AddSchemaWithId(schema, schema_id))
        {
            ack.code = mdsdinput::ACK_DUPLICATE_SCHEMA_ID;
            return ack;
        }
    }
    else
    {
        try
        {
            schema = _schema_cache->GetSchema(schema_id);
        }
        catch(std::out_of_range)
        {
            ack.code = mdsdinput::ACK_UNKNOWN_SCHEMA_ID;
            return ack;
        }
    }

    if (schema->fields.size() != jmsgdata.Size())
    {
        std::ostringstream msg;
        msg << "Invalid message data: Array size invalid: Expected " << schema->fields.size() << ", got " << jmsgdata.Size();
        throw std::runtime_error(msg.str());
    }

    ack.msgId = jmsgId.GetInt64();
    source = std::string(jsource.GetString(), jsource.GetStringLength());

    //
    for (int i = 0; i < (int)schema->fields.size(); ++i)
    {
        mdsdinput::FieldDef fd = schema->fields.at(i);
        const rapidjson::Value& val = jmsgdata[i];
        switch (fd.fieldType)
        {
            case mdsdinput::FT_INVALID:
                ack.code = mdsdinput::ACK_DECODE_ERROR;
                return ack;
            case mdsdinput::FT_BOOL:
                if (!val.IsBool())
                {
                    throw std::runtime_error("Invalid Message data");
                }
                ce.AddColumnIgnoreMetaData(fd.name, new MdsValue(val.GetBool()));
                break;
            case mdsdinput::FT_INT32:
                if (!val.IsInt())
                {
                    throw std::runtime_error("Invalid Message data");
                }
                ce.AddColumnIgnoreMetaData(fd.name, new MdsValue(static_cast<long>(val.GetInt())));
                break;
            case mdsdinput::FT_INT64:
                if (!val.IsInt64())
                {
                    throw std::runtime_error("Invalid Message data");
                }
                // The explicit cast is necessary. Without it, the value will get treated as mt_int32.
                ce.AddColumnIgnoreMetaData(fd.name, new MdsValue(static_cast<long long>(val.GetInt64())));
                break;
            case mdsdinput::FT_DOUBLE:
                if (!val.IsNumber())
                {
                    throw std::runtime_error("Invalid Message data");
                }
                ce.AddColumnIgnoreMetaData(fd.name, new MdsValue(val.GetDouble()));
                break;
            case mdsdinput::FT_TIME:
                if (!val.IsArray() || val.Size() != 2)
                {
                    throw std::runtime_error("Invalid Message data");
                }
                {
                    MdsTime time(val[0].GetUint64(), val[1].GetUint()/1000);
                    ce.AddColumnIgnoreMetaData(fd.name,  new MdsValue(time));
                    if (!schema->timestampFieldIdx.empty() && static_cast<uint32_t>(i) == *(schema->timestampFieldIdx))
                    {
                        ce.SetPreciseTime(time);
                    }
                }
                break;
            case mdsdinput::FT_STRING:
                if (!val.IsString())
                {
                    throw std::runtime_error("Invalid Message data");
                }
                ce.AddColumnIgnoreMetaData(fd.name, new MdsValue(std::string(val.GetString(), val.GetStringLength())));
                break;
            default:
                throw std::runtime_error("Invalid field type in schema");
        }
    }

    SchemaCache::IdType mdsdSchemaId;
    auto it = _id_map.find(schema_id);
    if (it != _id_map.end())
    {
        mdsdSchemaId = it->second;
    } else {
        mdsdSchemaId = schema_id_for_key(_schema_cache->GetSchemaKey(schema_id));
        _id_map.insert(std::make_pair(schema_id, mdsdSchemaId));
        TRACEINFO(trace, "Mapped connection schemaId ("+std::to_string(schema_id)+") to SchemaCache id ("+std::to_string(mdsdSchemaId)+")");
    }

    ce.SetSchemaId(mdsdSchemaId);

    ack.code = mdsdinput::ACK_SUCCESS;

    return ack;
}


mdsdinput::Ack
ProtocolHandlerJSON::handleMsg(msg_data_t& msg_data)
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerJSON::handleMsg");

    mdsdinput::Ack ack;
    std::string source;

    auto ce = std::make_shared<CanonicalEntity>();
    ce->SetPreciseTime(MdsTime::Now());

    try
    {
        ack = decodeMsg(msg_data, source, *ce);
    }
    catch(std::exception& ex)
    {
        std::ostringstream strm;
        strm << "ProtocolHandlerJSON: Error decoding message '";
        for(auto c: msg_data) {
            strm << c;
        }
        strm << "' from fd " << _fd << ": " << ex.what();

        Logger::LogWarn(strm);
        ack.code = mdsdinput::ACK_DECODE_ERROR;
    }

    if (ack.code == mdsdinput::ACK_SUCCESS)
    {

        auto sink = LocalSink::Lookup(source);
        if (!sink)
        {
            Logger::LogWarn("ProtocolHandlerJSON: Received an event from source \"" + source +
                            "\" not used elsewhere in the active configuration");
            ack.code = mdsdinput::ACK_INVALID_SOURCE;
        }
        else
        {
            TRACEINFO(trace, "Message added to LocalSink");
            sink->AddRow(ce);
        }
    }

    return ack;
}
