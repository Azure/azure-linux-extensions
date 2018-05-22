// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsdInputMessageBuilder.h"
#include "bond/core/bond.h"
#include <boost/make_shared.hpp>
#include <algorithm>

namespace mdsdinput
{

    void MessageBuilder::MessageBegin()
    {
        _output.reset(new bond::OutputBuffer(_buffer, BUFFER_SIZE));
        _writer.reset(new bond::SimpleBinaryWriter<bond::OutputBuffer>(*(_output.get())));
        _schema = std::make_shared<SchemaDef>();
    }

    std::shared_ptr<Message> MessageBuilder::MessageEnd(const std::string& source)
    {
        auto id = (_schema_cache->AddSchema(_schema)).first;
        auto msg = std::make_shared<Message>();

        msg->schemaId = id;
        msg->source = source;

        auto out = _output->GetBuffer();
        auto buf = boost::allocate_shared_noinit<char[]>(std::allocator<char>(), out.length());
        std::copy(out.begin(), out.end(), buf.get());
        msg->data.assign(buf, out.length());

        return msg;
    }

    void MessageBuilder::AddBool(const std::string& name, bool value)
    {
        FieldDef fd;
        fd.name = name;
        fd.fieldType = FT_BOOL;
        _schema->fields.push_back(fd);
        _writer->Write(value);
    }

    void MessageBuilder::AddInt32(const std::string& name, int32_t value)
    {
        FieldDef fd;
        fd.name = name;
        fd.fieldType = FT_INT32;
        _schema->fields.push_back(fd);
        _writer->Write(value);
    }

    void MessageBuilder::AddInt64(const std::string& name, int64_t value)
    {
        FieldDef fd;
        fd.name = name;
        fd.fieldType = FT_INT64;
        _schema->fields.push_back(fd);
        _writer->Write(value);
    }

    void MessageBuilder::AddDouble(const std::string& name, double value)
    {
        FieldDef fd;
        fd.name = name;
        fd.fieldType = FT_DOUBLE;
        _schema->fields.push_back(fd);
        _writer->Write(value);
    }

    void MessageBuilder::AddTime(const std::string& name, const Time& value, bool isTimestampField)
    {
        FieldDef fd;
        fd.name = name;
        fd.fieldType = FT_TIME;
        if (isTimestampField)
        {
            _schema->timestampFieldIdx.set(static_cast<uint32_t>(_schema->fields.size()));
        }
        _schema->fields.push_back(fd);
        _writer->Write(value.sec);
        _writer->Write(value.nsec);
    }

    void MessageBuilder::AddString(const std::string& name, const std::string& value)
    {
        FieldDef fd;
        fd.name = name;
        fd.fieldType = FT_STRING;
        _schema->fields.push_back(fd);
        _writer->Write(value);
    }

}
