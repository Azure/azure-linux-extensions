// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "EventHubUploaderId.hh"
#include <sstream>
#include <stdexcept>
#include <vector>
#include <boost/algorithm/string.hpp>
#include <boost/algorithm/string/split.hpp>

using namespace mdsd;

EventHubUploaderId::EventHubUploaderId(
    EventHubType ehtype,
    const std::string & moniker,
    const std::string & eventname
    ) :
        m_ehtype(ehtype),
        m_moniker(moniker),
        m_eventname(eventname)
{
    if (m_moniker.empty()) {
        throw std::invalid_argument("EventHubUploaderId: invalid empty moniker for event '" + m_eventname + "'");
    }
    if (m_eventname.empty()) {
        throw std::invalid_argument("EventHubUploaderId: invalid empty eventname for moniker '" + m_moniker + "'");
    }
}

EventHubUploaderId::EventHubUploaderId(const std::string & idstr)
{
    std::vector<std::string> fields;
    boost::algorithm::split(fields, idstr, boost::is_any_of(" "), boost::token_compress_on);

    constexpr size_t nExpected = 3;
    if (nExpected != fields.size()) {
        std::ostringstream strm;
        strm << "Invalid EHUploaderId '" << idstr << "' in number of tokens: expected=" <<
            nExpected << "; actual=" << fields.size();
        throw std::runtime_error(strm.str());
    }

    m_eventname = fields[0];
    m_moniker = fields[1];
    m_ehtype = EventHubTypeFromStr(fields[2]);
}
