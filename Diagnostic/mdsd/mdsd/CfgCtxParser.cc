// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxParser.hh"
#include "Utility.hh"
#include "MdsTime.hh"

using namespace CfgCtx;

std::map<std::string, CfgCtxParser::typeparser_t> CfgCtxParser::s_evtParsers = {
    { "account", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseName(iter->first, iter->second, p->m_account); }
    },
    { "dontUsePerNDayTable", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { p->m_isNoPerNDay = MdsdUtil::to_bool(iter->second); return true; }
    },
    { "duration", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseDuration(iter->first, iter->second); }
    },
    { "eventName", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseName(iter->first, iter->second, p->m_eventName); }
    },
    { "priority", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParsePriority(iter->first, iter->second); }
    },
    { "storeType", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseStoreType(iter->first, iter->second); }
    }
};

std::map<std::string, CfgCtxParser::typeparser_t>
CfgCtxParser::s_etwEvtParsers = BuildEtwParsersTable();

std::map<std::string, CfgCtxParser::typeparser_t>
CfgCtxParser::BuildEtwParsersTable()
{
    std::map<std::string, typeparser_t> tmp = s_evtParsers;
    tmp["id"] = [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseId(iter->first, iter->second); };
    return tmp;
}

std::map<std::string, CfgCtxParser::typeparser_t>
CfgCtxParser::s_etwProviderParsers = {
    { "format", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseName(iter->first, iter->second, p->m_format); }
    },
    { "guid", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseName(iter->first, iter->second, p->m_guid); }
    },
    { "priority", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParsePriority(iter->first, iter->second); }
    },
    { "storeType", [] (CfgCtxParser* p, const xmlattr_iter_t & iter) -> bool
        { return p->ParseStoreType(iter->first, iter->second); }
    }
};


bool
CfgCtxParser::ParseEvent(
    const xmlattr_t& properties,
    EventType eventType
    )
{
    if (!m_context) {
        return false;
    }

    bool resultOK = true;
    auto & parsersTable = (EventType::RouteEvent == eventType) ? s_evtParsers : s_etwEvtParsers;

    for (xmlattr_iter_t iter = properties.begin(); iter != properties.end(); ++iter) {
        auto parserIter = parsersTable.find(iter->first);
        if (parserIter != parsersTable.end()) {
            resultOK = resultOK && parserIter->second(this, iter);
        }
        else {
            LogUnexpectedAttrNameWarn(iter->first);
        }
    }

    // validate required attributes
    if (m_eventName.empty()) {
        LogRequiredAttrError("eventName");
        resultOK = false;
    }

    if (EventType::EtwEvent == eventType && m_eventId < 0) {
        LogRequiredAttrError("id");
        resultOK = false;
    }

    return resultOK;
}

bool
CfgCtxParser::ParseEtwProvider(
    const xmlattr_t& properties
    )
{
    if (!m_context) {
        return false;
    }

    bool resultOK = true;
    const char* supportedFormat = "EventSource"; // only this is supported for now

    for (xmlattr_iter_t iter = properties.begin(); iter != properties.end(); ++iter) {
        auto parserIter = s_etwProviderParsers.find(iter->first);
        if (parserIter != s_etwProviderParsers.end()) {
            resultOK = resultOK && parserIter->second(this, iter);
        }
        else {
            LogUnexpectedAttrNameWarn(iter->first);
        }
    }

    if (m_guid.empty()) {
        LogRequiredAttrError("guid");
        resultOK = false;
    }

    if (!m_format.empty() && supportedFormat != m_format) {
        LogInvalidValueError("format", m_format);
        resultOK = false;
    }

    return resultOK;
}

bool
CfgCtxParser::ParseName(
    const std::string & attrName,
    const std::string & attrValue,
    std::string & result)
{
    result = attrValue;
    if (MdsdUtil::NotValidName(result)) {
        result.clear();
        LogInvalidValueError(attrName, attrValue);
        return false;
    }
    return true;
}

bool
CfgCtxParser::ParseStoreType(const std::string & attrName, const std::string & attrValue)
{
    bool resultOK = true;

    m_storeType = StoreType::from_string(attrValue);
    if (StoreType::None == m_storeType) {
        LogInvalidValueError(attrName, attrValue);
        resultOK = false;
    }
    else {
        m_hasStoreType = true;
    }
    return resultOK;
}

bool
CfgCtxParser::ParsePriority(const std::string & attrName, const std::string & attrValue)
{
    m_hasPriority = true;
    if (!m_priority.Set(attrValue)) {
        LogUnknownAttrValueWarn(attrName, attrValue);
        m_hasPriority = false;
    }
    else if (0 == m_interval) {
        m_interval = m_priority.Duration();
    }
    return true;
}

bool
CfgCtxParser::ParseDuration(const std::string & attrName, const std::string & attrValue)
{
    m_interval = MdsTime::FromIS8601Duration(attrValue).to_time_t();

    if (0 == m_interval) {
        LogInvalidValueError(attrName, attrValue);
        return false;
    }
    else if (10 > m_interval) {
        m_context->WARNING("Minimum supported duration is ten (10) seconds; using minimum");
        m_interval = 10;
    }
    return true;
}

bool
CfgCtxParser::ParseId(const std::string & attrName, const std::string & attrValue)
{
    int tmp = atoi(attrValue.c_str());
    if (tmp < 0 || tmp > INT_MAX) {
        LogInvalidValueError(attrName, attrValue);
        return false;
    }
    else {
        m_eventId = tmp;
    }
    return true;
}
