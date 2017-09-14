// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CmdXmlParser.hh"
#include "CmdXmlElement.hh"

using namespace mdsd::details;

void
CmdXmlParser::OnEndElement(const std::string& name)
{
    switch(Name2ElementType(name)) {
        case ElementType::Verb:
            m_verb = MoveBody();
            break;
        case ElementType::Parameter:
            m_paramList.emplace_back(MoveBody());
            break;
        default:
            break;
    }
}
