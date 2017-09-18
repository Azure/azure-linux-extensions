// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>
#include <algorithm>
#include <cctype>

#include "CmdListXmlParser.hh"
#include "MdsException.hh"
#include "CmdXmlElement.hh"

using namespace mdsd::details;

void
CmdListXmlParser::OnEndElement(const std::string& name)
{
    switch(Name2ElementType(name)) {
        case ElementType::Verb:
            m_verb = MoveBody();
            break;
        case ElementType::Parameter:
            m_paramList.emplace_back(MoveBody());
            break;
        case ElementType::Command:        
            if (std::all_of(m_verb.cbegin(), m_verb.cend(), ::isspace)) {
                std::ostringstream strm;
                strm << "Invalid data in XML file '" << GetFilePath() 
                     << "': 'Verb' cannot be empty or whitespace.";
                throw MDSEXCEPTION(strm.str());
            }

            if (0 == m_paramList.size()) {
                std::ostringstream strm;
                strm << "Invalid data in XML file '" << GetFilePath() 
                     << "': no Parameter value is found.";
                throw MDSEXCEPTION(strm.str());
            }

            m_cmdParamMap[m_verb].emplace_back(m_paramList);
            m_paramList.clear();
            break;
        default:
            break;
    }
}
