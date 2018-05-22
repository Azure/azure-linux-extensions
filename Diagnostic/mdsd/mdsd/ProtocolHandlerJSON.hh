// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _PROTOCOL_HANDLER_JSON_HH_
#define _PROTOCOL_HANDLER_JSON_HH_

#include "ProtocolHandlerBase.hh"
#include "CanonicalEntity.hh"
#include "MdsdInputMessageIO.h"
#include "MdsdInputMessageDecoder.h"
#include "MdsdInputSchemaCache.h"
#include <array>

#include "rapidjson/document.h"
#include "rapidjson/stringbuffer.h"


/*
 * This class is not, nor is it intended to be, thread safe.
 *
 * ProtocolListenerDynamicJSON allocates a separate instance of this class per connection
 * and each connection is handled by a separate thread.
 */
class ProtocolHandlerJSON: public ProtocolHandlerBase
{
public:
    static constexpr size_t MAX_MSG_DATA_SIZE = 128 * 1024-1;
    typedef std::array<char, MAX_MSG_DATA_SIZE+1> msg_data_t;

    explicit ProtocolHandlerJSON(int fd)
        : _fd(fd), _schema_cache(std::make_shared<mdsdinput::SchemaCache>())
    {}

    ~ProtocolHandlerJSON();

    void Run();

private:
    size_t readMsgSize();
    void readMsgData(msg_data_t& msg_data, size_t size);

    void writeAck(uint64_t msgId, mdsdinput::ResponseCode rcode);

    mdsdinput::Ack decodeMsg(msg_data_t& msg_data, std::string& source, CanonicalEntity& ce);

    mdsdinput::Ack handleMsg(msg_data_t& msg_data);

    int _fd;
    std::shared_ptr<mdsdinput::SchemaCache> _schema_cache;
};

// vim: set ai sw=8:
#endif // _PROTOCOL_HANDLER_JSON_HH_
