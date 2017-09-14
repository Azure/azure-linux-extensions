// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __CMDXMLPARSER__HH__
#define __CMDXMLPARSER__HH__

#include <vector>
#include "BodyOnlyXmlParser.hh"

namespace mdsd { namespace details
{

/// <summary>
/// MDS Command XML parser. It will parse one <Command>...</Command>
/// For reference, check commands.xsd.
/// </summary>
class CmdXmlParser : public BodyOnlyXmlParser
{
public:
    CmdXmlParser() = default;
    ~CmdXmlParser() = default;

    std::string GetVerb() const { return m_verb; }

    std::vector<std::string> GetParamList() const { return m_paramList; }

private:
    void OnEndElement(const std::string& name) override;

private:
    std::string m_verb;  // The value of 'Verb'
    std::vector<std::string> m_paramList; // a list of the parameters defined for the Verb.
};

} // namespace details
} // namespace mdsd

#endif // __CMDXMLPARSER__HH__
