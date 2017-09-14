// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <bond/core/bond.h>
#include "EventData.hh"
#include "MdsException.hh"

using namespace mdsd;

static std::string
GetStringFromOutput(
    const bond::OutputBuffer & output
    )
{
    std::vector<bond::blob> blist;
    output.GetBuffers(blist);

    size_t totalLen = 0;
    for (const auto & b : blist) {
        totalLen += b.length();
    }

    std::string resultStr;
    resultStr.reserve(totalLen);
    for (const auto & b : blist) {
        resultStr.append(b.content(), b.length());
    }
    return resultStr;
}


std::string
EventDataT::Serialize() const
{
    if (m_data.empty()) {
        throw MDSEXCEPTION("EventData serialization failed: data cannot be empty.");
    }

    bond::OutputBuffer output;
    bond::SimpleBinaryWriter<bond::OutputBuffer> writer(output);
    writer.Write(m_data);

    writer.Write(static_cast<size_t>(m_table.size()));
    for (const auto & it : m_table) {
        writer.Write(it.first);
        writer.Write(it.second);
    }

    return GetStringFromOutput(output);
}

EventDataT
EventDataT::Deserialize(
    const std::string & datastr
    )
{
    return Deserialize(datastr.c_str(), datastr.size());
}

EventDataT
EventDataT::Deserialize(
    const char* buf,
    size_t bufSize
    )
{
    if (!buf) {
        throw MDSEXCEPTION("EventData deserialization failed: input buf cannot be NULL.");
    }

    EventDataT dataObj;

    try {
        bond::blob b;
        b.assign(buf, bufSize);

        bond::SimpleBinaryReader<bond::InputBuffer> reader(b);
        std::string datastr;
        reader.Read(datastr);
        dataObj.SetData(std::move(datastr));

        size_t tblSize = 0;
        reader.Read(tblSize);

        for (size_t i = 0; i < tblSize; i++) {
            std::string k, v;
            reader.Read(k);
            reader.Read(v);
            dataObj.AddProperty(std::move(k), std::move(v));
        }
    }
    catch(std::exception& ex) {
        throw MDSEXCEPTION(std::string("EventData deserialization failed: ") + ex.what());
    }

    return dataObj;
}
