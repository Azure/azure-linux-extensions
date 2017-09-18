// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ProtocolHandlerBond.hh"

#include <cassert>

#include "Logger.hh"
#include "MdsValue.hh"
#include "CanonicalEntity.hh"
#include "Trace.hh"
#include "LocalSink.hh"
#include "Utility.hh"

extern "C" {
#include <unistd.h>
}

ProtocolHandlerBond::~ProtocolHandlerBond()
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerBond::Destructor");
    close(_fd);
    Logger::LogInfo(std::string("ProtocolHandlerBond: Connection on ") + std::to_string(_fd) +  " closed");
}

void ProtocolHandlerBond::Run()
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerBond::Run");
    while(true)
    {
        try
        {
            mdsdinput::Message msg;
            mdsdinput::Ack ack;

            // Read message
            _io.ReadMessage(msg);

            // Process message
            ack.msgId = msg.msgId;
            ack.code = handleEvent(msg);

            // Ack message
            _io.WriteAck(ack);
        }
        catch (mdsdinput::eof_exception)
        {
            Logger::LogInfo(std::string("ProtocolHandlerBond: EOF on ") + std::to_string(_fd));
            return;
        }
        catch (mdsdinput::msg_too_large_error)
        {
            Logger::LogWarn(std::string("ProtocolHandlerBond: Received oversized message on ") + std::to_string(_fd));
            return;
        }
        catch (std::exception& ex)
        {
            Logger::LogError(std::string("ProtocolHandlerBond: Unexpected exception while processing messages on ") + std::to_string(_fd) + ": " + ex.what());
            return;
        }
    }
}

class FieldReceiver
{
public:
    FieldReceiver(CanonicalEntity& ce)
        : _ce(ce)
    {}

    void BoolField(const std::string& name, bool value)
    {
        _ce.AddColumnIgnoreMetaData(name, new MdsValue(value));
    }

    void Int32Field(const std::string& name, int32_t value)
    {
        _ce.AddColumnIgnoreMetaData(name, new MdsValue(static_cast<long>(value)));
    }

    void Int64Field(const std::string& name, int64_t value)
    {
        // The explicit cast is necessary. Without it, the value will get treated as mt_int32.
        _ce.AddColumnIgnoreMetaData(name, new MdsValue(static_cast<long long>(value)));
    }

    void DoubleField(const std::string& name, double value)
    {
        _ce.AddColumnIgnoreMetaData(name, new MdsValue(value));
    }

    void TimeField(const std::string& name, const mdsdinput::Time& value, bool isTimestampField)
    {
        MdsTime time(value.sec, value.nsec/1000);
        _ce.AddColumnIgnoreMetaData(name, new MdsValue(time));
        if (isTimestampField)
        {
            _ce.SetPreciseTime(time);
        }
    }

    void StringField(const std::string& name, const std::string& value)
    {
        _ce.AddColumnIgnoreMetaData(name, new MdsValue(value));
    }
private:
    CanonicalEntity& _ce;
};

mdsdinput::ResponseCode
ProtocolHandlerBond::handleEvent(const mdsdinput::Message& msg)
{
    Trace trace(Trace::EventIngest, "ProtocolHandlerBond::handleEvent");

    TRACEINFO(trace, "Received msg {MsgId: " << msg.msgId << ", Source: " << msg.source << "}");

    auto sink = LocalSink::Lookup(msg.source);
    if (!sink)
    {
        Logger::LogWarn("Received an event from source \"" + msg.source + "\" not used elsewhere in the active configuration");
        return mdsdinput::ACK_INVALID_SOURCE;
    }

    // This check may be overly restrictive.
    // Perhaps we should allow it if the message's dynamically defined schema matches the predefined schema.
    if (sink->SchemaId() != 0)
    {
        Logger::LogWarn("ProtocolHandlerBond: Received an event from source \"" + msg.source + "\" that is not valid for dynamic schema input");
        return mdsdinput::ACK_INVALID_SOURCE;
    }

    auto ce = std::make_shared<CanonicalEntity>();
    ce->SetPreciseTime(MdsTime::Now());

    FieldReceiver fr(*ce);
    auto responseCode = _decoder.Decode(msg, fr);
    if (mdsdinput::ACK_SUCCESS == responseCode)
    {
        SchemaCache::IdType schemaId;
        auto it = _id_map.find(msg.schemaId);
        if (it != _id_map.end())
        {
            schemaId = it->second;
        } else {
            schemaId = schema_id_for_key(_decoder.GetSchemaKey(msg.schemaId));
            _id_map.insert(std::make_pair(msg.schemaId, schemaId));
            TRACEINFO(trace, "Mapped connection schemaId (" << msg.schemaId << ") to SchemaCache id (" << schemaId << ")");
        }

        ce->SetSchemaId(schemaId);

        TRACEINFO(trace, "Message added to LocalSink with schemaId (" << schemaId << ")");
        sink->AddRow(ce);
    }

    return responseCode;
}
