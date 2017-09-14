// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxEtw.hh"
#include "MdsdConfig.hh"
#include "CfgCtxParser.hh"
#include "LocalSink.hh"
#include "Subscription.hh"
#include "PipeStages.hh"
#include "EtwEvent.hh"
#include "EventType.hh"

////////////////// CfgCtxEtwProviders

subelementmap_t CfgCtxEtwProviders::s_subelements = {
    { "EtwProvider", [] (CfgContext* parent) -> CfgContext* { return new CfgCtxEtwProvider(parent); } }
};

std::string CfgCtxEtwProviders::s_name = "EtwProviders";

////////////////// CfgCtxEtwProvider

std::string CfgCtxEtwProvider::s_name = "EtwProvider";

subelementmap_t CfgCtxEtwProvider::s_subelements = {
    {"Event", [] (CfgContext* parent) -> CfgContext * { return new CfgCtxEtwEvent(parent); } }
};

void
CfgCtxEtwProvider::Enter(const xmlattr_t& properties)
{
    CfgCtx::CfgCtxParser parser(this);
    if (!parser.ParseEtwProvider(properties)) {
        return;
    }

    m_guid = parser.GetGuid();
    m_priority = parser.GetPriority();

    if (parser.HasStoreType()) {
        m_storeType = parser.GetStoreType();
    }
}

CfgContext*
CfgCtxEtwProvider::Leave()
{
    return ParentContext;
}

////////////////// CfgCtxEtwEvent
subelementmap_t CfgCtxEtwEvent::s_subelements;
std::string CfgCtxEtwEvent::s_name = "Event";

void
CfgCtxEtwEvent::Enter(const xmlattr_t& properties)
{
    CfgCtx::CfgCtxParser parser(this);
    if (!parser.ParseEvent(properties, CfgCtx::EventType::EtwEvent)) {
        return;
    }

    CfgCtxEtwProvider *parent = dynamic_cast<CfgCtxEtwProvider*>(ParentContext);
    if (!parent) {
        FATAL("Found <" + s_name + "> in <" + ParentContext->Name() + ">; that can't happen.");
        return;
    }

    auto guidstr = parent->GetGuid();
    if (guidstr.empty()) {
        ERROR("<" + s_name + "> missed required GUID attribute.");
        return;
    }

    if (parser.HasStoreType()) {
        m_storeType = parser.GetStoreType();
    }
    else {
        m_storeType = parent->GetStoreType();
    }

    if (StoreType::None == m_storeType) {
        m_storeType = StoreType::XTable;
    }

    Priority priority;
    if (parser.HasPriority()) {
        priority = parser.GetPriority();
    }
    else {
        priority = parent->GetPriority();
    }

    m_eventId = parser.GetEventId();

    // for ETW, use local table name as LocalSink source.
    std::string source = EtwEvent::BuildLocalTableName(guidstr, m_eventId);
    m_sink = LocalSink::Lookup(source);
    if (!m_sink) {
        m_sink = new LocalSink(source);
	m_sink->AllocateSchemaId();
    }

    bool isNoPerNDay = parser.IsNoPerNDay();
    std::string account = parser.GetAccount();
    std::string eventName = parser.GetEventName();
    time_t interval = parser.GetInterval();

    try {
        auto target = MdsEntityName { eventName, isNoPerNDay, Config, account, m_storeType };
        m_subscription = new Subscription(m_sink, std::move(target), priority, MdsTime(interval));

        if (StoreType::Local != m_storeType) {
            m_subscription->AddStage(new Pipe::Identity(Config->GetIdentityVector()));
        }
        Config->AddMonikerEventInfo(account, eventName, m_storeType, source, mdsd::EventType::EtwEvent);
    }
    catch(const std::invalid_argument& ex) {
        ERROR(ex.what());
        return;
    }
    catch(...) {
        FATAL("Unknown exception; skipping.");
        return;
    }
}

CfgContext*
CfgCtxEtwEvent::Leave()
{
    if (!m_subscription) {
        return ParentContext;
    }

    if (StoreType::XTable == m_storeType) {
        m_subscription->AddStage(new Pipe::BuildSchema(Config, m_subscription->target(), true));
    }

    Batch* batch = Config->GetBatch(m_subscription->target(), m_subscription->Duration());
    if (batch) {
        m_subscription->AddStage(new Pipe::BatchWriter(batch, Config->GetIdentityVector(),
                                                       Config->PartitionCount(), m_storeType));
        Config->AddTask(m_subscription);
    }
    else {
        ERROR("Unable to create routing for " + s_name + " id=" + std::to_string(m_eventId));
    }

    return ParentContext;
}
