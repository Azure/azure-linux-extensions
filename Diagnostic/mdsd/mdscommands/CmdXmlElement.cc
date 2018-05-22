// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CmdXmlElement.hh"
#include <unordered_map>

using namespace mdsd::details;

static std::unordered_map<std::string, ElementType> & GetCmdElementTypeMap()
{
    static auto xmltable = new std::unordered_map<std::string, ElementType>(
    {
        { "Verb", ElementType::Verb },
        { "Parameter", ElementType::Parameter },
        { "Command", ElementType::Command }
    });
    return *xmltable;
}


ElementType
mdsd::details::Name2ElementType(const std::string& name)
{
    auto xmltable = GetCmdElementTypeMap();
    auto iter = xmltable.find(name);
    if (iter != xmltable.end()) {
        return iter->second;
    }
    return ElementType::Unknown;
}
