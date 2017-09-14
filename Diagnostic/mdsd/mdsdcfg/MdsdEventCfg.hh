// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __MDSDEVENTCFG__HH__
#define __MDSDEVENTCFG__HH__

#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "EventSinkCfgInfo.hh"
#include "CfgEventAnnotationType.hh"


namespace mdsd
{

enum class EventType;

/// This class handles general mdsd event configurations.
/// Usage pattern:
/// - Collect raw event info data: AddEventSinkCfgInfoItem(), SetEventAnnotationTypes(),
///   UpdateMoniker(), etc.
/// - Use aggregated results: GetCentralBondEvents(), IsEventHubEnabled(), etc.
///   The event configuration data are lazily extracted and aggregated at "Get" time.
///
/// NOTE: This class is not designed for thread-safe.
///
class MdsdEventCfg {
public:
    MdsdEventCfg() = default;
    ~MdsdEventCfg() = default;

    /// <summary>
    /// Add an eventSinkCfgInfo object to internal data structure if it is valid.
    /// Throw exception if eventSinkCfgInfo is invalid.
    /// </summary>
    void AddEventSinkCfgInfoItem(const EventSinkCfgInfo & item);

    /// <summary>
    /// Set event annotation types object.
    /// </summary>
    void SetEventAnnotationTypes(std::unordered_map<std::string, EventAnnotationType::Type>&& eventtypes);

    /// <summary>
    /// For all m_eventSinkCfgInfoList entries where eventName='eventName'
    /// and moniker='oldMoniker', update moniker to 'newMoniker'.
    /// Throw exception if any input parameter string is empty.
    /// </summary>
    void UpdateMoniker(const std::string & eventName, const std::string & oldMoniker,
        const std::string & newMoniker);

    /// <summary>
    /// Get a map of <eventname, monikers> for all CentralBond store type events.
    /// </summary>
    std::unordered_map<std::string, std::unordered_set<std::string>> GetCentralBondEvents() const;

    /// <summary>
    /// Return the names of all event publishers in mdsd xml <EventStreamingAnnotations>.
    /// This includes anything that could be invalid if any.
    /// </summary>
    std::unordered_set<std::string> GetEventPublishers() const
    {
        return m_eventPublishers;
    }

    /// <summary>
    /// Return all the monikers used by given publisherName, which can be either a source name,
    /// or an EventName (e.g. OMIQuery or DerivedEvent).
    /// Return empty set if publisherName is not found
    /// </summary>
    std::unordered_set<std::string> GetEventPubMonikers(const std::string & publisherName);

    /// <summary>
    /// Get invalid names in mdsd xml <EventStreamingAnnotations>
    /// </summary>
    std::unordered_set<std::string> GetInvalidAnnotations();

    /// <summary>
    /// Returns boolean specifying whether provided moniker (input parameter)
    /// has a companion Event Hub.
    /// </summary>
    bool IsEventHubEnabled(const std::string & moniker)
    {
        ExtractEventCfg();
        return m_ehMonikers.count(moniker);
    }

    size_t GetNumEventSinkCfgInfoItems() const
    {
        return m_eventSinkCfgInfoList.size();
    }

private:
    /// <summary>
    /// Extract event configuration data and store them to internal data structures.
    /// - a set to store all the event names.
    /// - publisher name -> monikers map for all events.
    /// - All monikers that are used by EventHub notice or Event publishing.
    /// </summary>
    void ExtractEventCfg();

private:
    /// Whether any config data are updated
    bool m_dataUpdated = false;

    /// Store information about all the events in mdsd xml file.
    std::vector<EventSinkCfgInfo> m_eventSinkCfgInfoList;

    /// Store all the eventNames
    std::unordered_set<std::string> m_eventNames;

    /// This map tracks all the EventHub publication monikers to which each new
    /// CanonicalEvent, when added to the LocalSink, should be published.
    ///
    /// map key: LocalSink name
    /// map value: all the monikers used by the LocalSink
    std::unordered_map<std::string, std::unordered_set<std::string>> m_ehpubMonikers;

    /// key: item name; value: EventAnnotationType
    std::unordered_map<std::string, EventAnnotationType::Type> m_eventAnnotationTypes;

    /// Store all the event publisher names.
    std::unordered_set<std::string> m_eventPublishers;

    /// Store the moniker names when EventHub is enabled on the moniker:
    /// A companion Event Hub exists if
    /// - a moniker has an event of store type 'CentralBond'
    /// - a moniker has an event of store type 'Local', which is also listed
    ///   under EventStreamingAnnotation as an EventPublisher.
    std::unordered_set<std::string> m_ehMonikers;
};

} // namespace

#endif // __MDSDEVENTCFG__HH__
