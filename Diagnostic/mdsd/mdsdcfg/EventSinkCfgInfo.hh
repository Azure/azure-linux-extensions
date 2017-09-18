// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTSINKCFGINFO__HH__
#define __EVENTSINKCFGINFO__HH__

#include <string>
#include "StoreType.hh"
#include "EventType.hh"

namespace mdsd
{

// This class is about mdsd event sink/destination configuration info.
// It records what's defined in mdsd xml.
struct EventSinkCfgInfo {
    std::string m_eventName;
    std::string m_moniker;
    StoreType::Type m_storeType = StoreType::None;
    std::string m_sourceName;
    EventType m_eventType;

    EventSinkCfgInfo(const std::string & eventName,
        const std::string & moniker,
        StoreType::Type storeType,
        const std::string & sourceName,
        EventType eventType
        ) :
        m_eventName(eventName),
        m_moniker(moniker),
        m_storeType(storeType),
        m_sourceName(sourceName),
        m_eventType(eventType)
        {}

    /// Return true if this is a valid entry. Return false otherwise.
    /// NOTE: sourceName can be empty (e.g. OMIQuery).
    bool IsValid() const
    {
        if (m_moniker.empty() ||
            StoreType::None == m_storeType ||
            (EventType::None == m_eventType && !m_eventName.empty()) ||
            (EventType::None != m_eventType && m_eventName.empty())
            ) {
            return false;
        }
        return true;
    }

    bool operator==(const EventSinkCfgInfo& other) const
    {
        return ((m_eventName == other.m_eventName) &&
                (m_moniker == other.m_moniker) &&
                (m_storeType == other.m_storeType) &&
                (m_sourceName == other.m_sourceName) &&
                (m_eventType == other.m_eventType)
                );
    }

    bool operator!=(const EventSinkCfgInfo& other) const
    {
        return  !(*this == other);
    }

    // Return the name of the local sink that holds the CanonicalEntities
    // that are supposed to be pushed to EventHub.
    // For OMIQuery and DerivedEvent events, this is their event name.
    // For other events, this is their source name.
    std::string GetLocalSinkName() const
    {
        if (EventType::OMIQuery != m_eventType &&
            EventType::DerivedEvent != m_eventType) {
            return m_sourceName;
        }
        else {
            return m_eventName;
        }
    }
};

} // namespace

#endif // __EVENTSINKCFGINFO__HH__
