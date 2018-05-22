// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#include "mdsd_input_reflection.h"
#include <string>
#include "MdsdInputSchemaCache.h"

namespace mdsdinput
{

    class MessageBuilder
    {
    public:
        static const size_t BUFFER_SIZE = 32 * 1024;

        MessageBuilder()
            : _schema_cache(std::make_shared<SchemaCache>())
            , _buffer(boost::make_shared_noinit<char[]>(BUFFER_SIZE))
        {}

        MessageBuilder(std::shared_ptr<SchemaCache>& schemaCache)
            : _schema_cache(schemaCache)
            , _buffer(boost::make_shared_noinit<char[]>(BUFFER_SIZE))
        {}

        MessageBuilder(const MessageBuilder&) = delete;
        MessageBuilder(MessageBuilder&&) = default;
        MessageBuilder& operator=(const MessageBuilder&) = delete;
        MessageBuilder& operator=(MessageBuilder&&) = default;

        std::shared_ptr<SchemaCache> GetSchemaCache() { return _schema_cache; }

        // Start a new message. All previous data is discarded.
        void MessageBegin();

        // Return a constructed message.
        std::shared_ptr<Message> MessageEnd(const std::string& source);

        void AddBool(const std::string& name, bool value);
        void AddInt32(const std::string& name, int32_t value);
        void AddInt64(const std::string& name, int64_t value);
        void AddDouble(const std::string& name, double value);
        void AddTime(const std::string& name, const Time& value, bool isTimestampField);
        void AddString(const std::string& name, const std::string& value);

    protected:
        std::shared_ptr<SchemaCache> _schema_cache;
        std::shared_ptr<SchemaDef> _schema;
        boost::shared_ptr<char[]> _buffer;
        std::unique_ptr<bond::OutputBuffer> _output;
        std::unique_ptr<bond::SimpleBinaryWriter<bond::OutputBuffer> > _writer;
    };

}
