// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef _CFGCTXPARSER_HH_
#define _CFGCTXPARSER_HH_

#include "ConfigParser.hh"
#include <map>
#include <functional>

#include "StoreType.hh"
#include "Priority.hh"
#include "CfgContext.hh"

extern "C" {
#include <time.h>
}

namespace CfgCtx {

/// mdsd Event types
enum class EventType {
    RouteEvent,
    EtwEvent
};



/// A utility class to parse mdsd configuration XML.
/// It implements parsing routines for common XML properties like
/// priority, storeType, etc.
class CfgCtxParser {
    using typeparser_t = std::function<bool (CfgCtxParser*, xmlattr_iter_t&)>;
public:
    /// <summary>
    /// Create a new parser instance.
    /// </summary>
    /// <param name='context'>Context where the parser is called. </param>
    CfgCtxParser(CfgContext * context) :
        m_context(context)
        {
        }

    ~CfgCtxParser() {}

    /// <summary>
    /// Parse properties of an EventType. After parsing, the results will
    /// be available from GetXXX() functions.
    /// </summary>
    /// <param name='properties'> properties to parse </param>
    /// <param name='eventType'> EventType </param>
    /// Return true if no error, false if any error.
    bool ParseEvent(const xmlattr_t& properties,
                    EventType eventType);

    /// <summary>
    /// Parse <EtwProvider ...> XML configuration.
    /// </summary>
    /// <param name='properties'> properties to parse </param>
    /// Return true if no error, false if any error.
    bool ParseEtwProvider(const xmlattr_t& properties);

    std::string GetAccount() const { return m_account; }
    bool IsNoPerNDay() const { return m_isNoPerNDay; }
    time_t GetInterval() const { return (0 == m_interval)? m_priority.Duration() : m_interval; }

    std::string GetEventName() const { return m_eventName; }
    std::string GetFormat() const { return m_format; }
    std::string GetGuid() const { return m_guid; }

    int GetEventId() const { return m_eventId; }

    Priority GetPriority() const { return m_priority; }
    bool HasPriority() const { return m_hasPriority; }

    StoreType::Type GetStoreType() const { return m_storeType; }
    bool HasStoreType() const { return m_hasStoreType; }


private:
    bool ParseName(const std::string & attrName,
                   const std::string & attrValue,
                   std::string & result);

    bool ParsePriority(const std::string & attrName,
                       const std::string & attrValue);

    bool ParseStoreType(const std::string & attrName,
                        const std::string & attrValue);

    bool ParseDuration(const std::string & attrName,
                       const std::string & attrValue);

    bool ParseId(const std::string & attrName,
                 const std::string & attrValue);

    void LogInvalidValueError(const std::string & attrName,
                              const std::string & attrValue)
    {
        m_context->ERROR("<" + m_context->Name() + "> attribute '" + attrName +
            "' has invalid value '" + attrValue + "'.");
    }

    void LogUnknownAttrValueWarn(const std::string & attrName,
                                 const std::string & attrValue)
    {
        m_context->WARNING("<" + m_context->Name() + ">: ignoring unknown '" +
            attrName + "'' value '" + attrValue + "'");
    }

    void LogRequiredAttrError(const std::string & attrName)
    {
        m_context->ERROR("<" + m_context->Name() + "> requires attribute '" + attrName + "'");
    }

    void LogUnexpectedAttrNameWarn(const std::string & attrName)
    {
        m_context->WARNING("<" + m_context->Name() +
            "> ignoring unexpected attribute '" + attrName + "'.");
    }

    static std::map<std::string, typeparser_t> BuildEtwParsersTable();

private:
    CfgContext * const m_context;

    std::string m_account;
    bool m_isNoPerNDay = false;
    time_t m_interval = 0;

    std::string m_eventName;
    std::string m_format;
    std::string m_guid;

    int m_eventId = -1;

    Priority m_priority;
    bool m_hasPriority = false;

    StoreType::Type m_storeType = StoreType::None;
    bool m_hasStoreType = false;

    static std::map<std::string, typeparser_t> s_evtParsers;
    static std::map<std::string, typeparser_t> s_etwEvtParsers;
    static std::map<std::string, typeparser_t> s_etwProviderParsers;
};

} // namespace CfgCtx

#endif // _CFGCTXPARSER_HH_
