// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>
#include "EventHubCmd.hh"
#include "MdsBlobReader.hh"
#include "CmdListXmlParser.hh"
#include "CmdXmlCommon.hh"
#include "MdsException.hh"
#include "Trace.hh"
#include "Logger.hh"

using namespace mdsd;
using namespace mdsd::details;

std::string EventHubCmd::s_parentContainerName = "mdssubscriptions";

std::ostream&
operator<<(std::ostream& str, const EhCmdXmlItems & cmd)
{
    // for security reason, only dump part of SAS key.
    str << "SAS key: " << cmd.sas.substr(0, 20) << "..., MDS Endpoint ID: "
        << cmd.endpoint << ", Mapped Moniker: " << cmd.moniker;
    return str;
}

EventHubCmd::EventHubCmd(
    std::string eventNameSpace,
    int eventVersion,
    std::string rootContainerSas
    ) :
    m_blobNameSuffix(std::move(eventNameSpace)),
    m_rootContainerSas(std::move(rootContainerSas)),
    m_noticeXmlItemsTable(new EhCmdXmlItemsTable_t()),
    m_pubXmlItemsTable(new EhCmdXmlItemsTable_t())
{
    if (m_blobNameSuffix.empty()) {
        throw MDSEXCEPTION("Event Hub MDS namespace cannot be empty.");
    }
    if (m_rootContainerSas.empty()) {
        throw MDSEXCEPTION("Event Hub blob root container cannot be empty.");
    }
    m_blobNameSuffix.append("Ver");
    m_blobNameSuffix.append(std::to_string(eventVersion));
    m_blobNameSuffix.append("v0.xml");
}

void
EventHubCmd::ProcessCmdXml()
{
    Trace trace(Trace::MdsCmd, "EventHubCmd::ProcessCmdXml");
    // The MACommandPub<ConfigId>.xml contains both notice and publish EH event info.
    ProcessBlob(GetBlobName("MACommandPub"));
}

void
EventHubCmd::ProcessBlob(
    std::string&& blobName
    )
{
    Trace trace(Trace::MdsCmd, "EventHubCmd::ProcessBlob");
    MdsBlobReader blobReader(m_rootContainerSas, std::move(blobName), s_parentContainerName);

    std::string blobData;
    const int ntimes = 5;

    // Because typically EventHubCmd XML blob should be OK to read, if empty data is returned,
    // retry to avoid any possible storage API failures.
    for (int i = 0; i < ntimes; i++) {
        blobData = std::move(blobReader.ReadBlobToString());

        if (!blobData.empty() || (ntimes-1) == i) {
            break;
        }

        TRACEINFO(trace, "No EventHubCmd XML is found. Retry index=" << (i+1));
        usleep(100*1000*(1<<i)); // exponential retry
    }
    if (blobData.empty()) {
        throw MDSEXCEPTION("EventHubCmd::ProcessBlob() failed to get blob " + blobName);
    }

    ParseCmdXml(std::move(blobData));
}

void
EventHubCmd::ParseCmdXml(
    std::string && xmlDoc
    )
{
    Trace trace(Trace::MdsCmd, "EventHubCmd::ParseCmdXml");
    if (xmlDoc.empty()) {
        throw MDSEXCEPTION("EventHubCmd::ParseCmdXml(): unexpected empty XML doc");
    }

    CmdListXmlParser parser;
    parser.Parse(xmlDoc);

    auto paramTable = parser.GetCmdParams();
    if (0 == paramTable.size()) {
        throw MDSEXCEPTION("No Command Parameter is found in Event Hub XML.");
    }

    // index starts with 0
    constexpr auto NPARAMSNotice = 13;
    constexpr auto NPARAMSPub = 9;

    constexpr auto EventNameIndexNotice = 6;
    constexpr auto EventNameIndexPub = 4;

    constexpr auto SASIndexNotice = 8;
    constexpr auto SASIndexPub = 5;

    constexpr auto MdsMonikerIndexNotice = 10;
    constexpr auto MdsMonikerIndexPub = 6;

    // example Endpoint value "Test". NOTE: this is not the full endpoint URL.
    constexpr auto MdsEndpointIdIndexNotice = 11;
    constexpr auto MdsEndpointIdIndexPub = 7;

    const std::string NoticeVerb = "SubscribeToEventHubEvent";
    const std::string PublisherVerb = "SubscribeToEventPublisherEvent";

    auto noticeParamsList = paramTable[NoticeVerb];
    ValidateCmdBlobParamsList(noticeParamsList, NoticeVerb, NPARAMSNotice);

    TRACEINFO(trace, "EventHub dump verb " << NoticeVerb << ":");
    for (const auto & v : noticeParamsList) {
        EhCmdXmlItems xmlItems { v[SASIndexNotice], v[MdsEndpointIdIndexNotice], v[MdsMonikerIndexNotice] };
        m_noticeXmlItemsTable->emplace(v[EventNameIndexNotice], xmlItems);
        TRACEINFO(trace, v[EventNameIndexNotice] << "'s " << xmlItems);
    }

    // Older version of MA may not have PublisherVerb
    auto pubParamsList = paramTable[PublisherVerb];
    if (0 == pubParamsList.size()) {
        Logger::LogInfo("No " + PublisherVerb + " is found.");
        return;
    }

    ValidateCmdBlobParamsList(pubParamsList, PublisherVerb, NPARAMSPub);

    TRACEINFO(trace, "EventHub dump verb " << PublisherVerb << ":");
    for (const auto & v : pubParamsList) {
        EhCmdXmlItems xmlItems { v[SASIndexPub], v[MdsEndpointIdIndexPub], v[MdsMonikerIndexPub] };
        m_pubXmlItemsTable->emplace(v[EventNameIndexPub], xmlItems);
        TRACEINFO(trace, v[EventNameIndexPub] << "'s " << xmlItems);
    }
}
