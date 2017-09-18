// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __CMDLISTXMLPARSER__HH__
#define __CMDLISTXMLPARSER__HH__

#include <vector>
#include <unordered_map>

#include "BodyOnlyXmlParser.hh"

namespace mdsd { namespace details
{

/// <summary>
/// Commands XML parser. It will parse <Commands>...</Commands>.
/// For reference, check commands.xsd.
/// </summary>
class CmdListXmlParser : public BodyOnlyXmlParser
{
public:
    /// map key: Verb name. map value: list of parameter-list.
    using CmdParamsType = std::unordered_map<std::string, std::vector<std::vector<std::string>>>;

    CmdListXmlParser() = default;

    ~CmdListXmlParser() = default;

    CmdParamsType GetCmdParams() const { return m_cmdParamMap; }

private:
    void OnEndElement(const std::string& name) override;

private:
    CmdParamsType m_cmdParamMap;          // store all verb names and all parameters.
    std::string m_verb;                   // store current verb name in the parser.
    std::vector<std::string> m_paramList; // store current parameter list in the parser.
};

} // namespace details
} // namespace mdsd

#endif // __CMDLISTXMLPARSER__HH__

