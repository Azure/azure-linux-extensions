// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTHUBCMD__HH__
#define __EVENTHUBCMD__HH__

#include <string>
#include <unordered_map>
#include <memory>
#include <iostream>

namespace mdsd
{

// Encapsulating type for EH cmd XML items
struct EhCmdXmlItems
{
    std::string sas;        // SAS key
    std::string endpoint;   // MDS endpoint ID (e.g., "Test", "Prod", "Stage", ...)
    std::string moniker;    // The mapped storage moniker (may be different from config file account moniker)
};

/// <summary>
/// This class implements functions to handle Event Hub Commands xml files.
/// This includes download xml file, parse xml file, and get data from xml.
/// </summary>
class EventHubCmd
{
public:
    using EhCmdXmlItemsTable_t = std::unordered_map<std::string, EhCmdXmlItems>;

    /// <summary>
    /// Create the object that'll handle Event Hub command xml file.
    /// <param name="eventNameSpace"> event name space</param>
    /// <param name="eventVersion"> event version<param>
    /// <param name="rootContainerSas"> the sas key for the root container
    /// where the command xml file locates. </param>
    /// </summary>
    EventHubCmd(std::string eventNameSpace,
                int eventVersion,
                std::string rootContainerSas);

    ~EventHubCmd() {}

    EventHubCmd(const EventHubCmd & other) = default;
    EventHubCmd(EventHubCmd&& other) = default;
    EventHubCmd& operator=(const EventHubCmd& other) = default;
    EventHubCmd& operator=(EventHubCmd&& other) = default;

    /// <sumamry>
    /// Process the Event Hub command XML to extract SASKey and other info.
    /// </summary>
    void ProcessCmdXml();

    /// <sumamry>
    /// Get Event Hub SAS Keys and return it in table.
    /// table: key=EventName; value: EH cmd XML items (currently SAS and MDS endpoint ID)
    /// </summary>
    std::shared_ptr<EhCmdXmlItemsTable_t> GetNoticeXmlItemsTable() const { return m_noticeXmlItemsTable; }
    std::shared_ptr<EhCmdXmlItemsTable_t> GetPublisherXmlItemsTable() const { return m_pubXmlItemsTable; }

    static void SetParentContainerName(std::string name) { s_parentContainerName = std::move(name); }

private:
    std::string GetBlobName(std::string baseName) { return baseName.append(m_blobNameSuffix); }

    void ProcessBlob(std::string&& blobName);

    void ParseCmdXml(std::string&& xmlDoc);

private:
    std::string m_blobNameSuffix;
    std::string m_rootContainerSas;

    // key = EventName; value: EH cmd XML items (currently SAS and MDS endpoint ID)
    std::shared_ptr<EhCmdXmlItemsTable_t> m_noticeXmlItemsTable;
    std::shared_ptr<EhCmdXmlItemsTable_t> m_pubXmlItemsTable;

    static std::string s_parentContainerName;
};

} // namespace mdsd

std::ostream&
operator<<(std::ostream& str, const mdsd::EhCmdXmlItems & cmd);

#endif // __EVENTHUBCMD__HH__
