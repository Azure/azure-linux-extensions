// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef _CFGCTXETW_HH_
#define _CFGCTXETW_HH_

#include "CfgContext.hh"
#include "CfgCtxError.hh"
#include "StoreType.hh"
#include "Priority.hh"

class CfgCtxEtwProviders : public CfgContext
{
public:
    CfgCtxEtwProviders(CfgContext * config) : CfgContext(config) {}
    virtual ~CfgCtxEtwProviders() {}

    virtual const std::string& Name() const { return s_name; }
    static const std::string& XmlName() { return s_name; }
    virtual const subelementmap_t& GetSubelementMap() const { return s_subelements; }

    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
    static subelementmap_t s_subelements;
    static std::string s_name;
};

class CfgCtxEtwProvider : public CfgContext
{
public:
    CfgCtxEtwProvider(CfgContext * config) : CfgContext(config) {}
    virtual ~CfgCtxEtwProvider() {}

    virtual const std::string& Name() const { return s_name; }
    static const std::string& XmlName() { return s_name; }

    virtual const subelementmap_t& GetSubelementMap() const
    {
        return (m_guid.empty()? CfgCtxError::subelements : s_subelements);
    }

    void Enter(const xmlattr_t& properties);
    CfgContext* Leave();

    std::string GetGuid() const { return m_guid; }
    StoreType::Type GetStoreType() const { return m_storeType; }
    Priority GetPriority() const { return m_priority; }

private:
    static subelementmap_t s_subelements;
    static std::string s_name;

    std::string m_guid;
    StoreType::Type m_storeType = StoreType::None;
    Priority m_priority;
};

class CfgCtxEtwEvent : public CfgContext
{
public:
    CfgCtxEtwEvent(CfgContext * config) : CfgContext (config) {}
    virtual ~CfgCtxEtwEvent() {}

    virtual const std::string& Name() const { return s_name; }
    static const std::string& XmlName() { return s_name; }
    virtual const subelementmap_t& GetSubelementMap() const { return s_subelements; }

    void Enter(const xmlattr_t& properties);
    CfgContext* Leave();

private:
    static subelementmap_t s_subelements;
    static std::string s_name;

    StoreType::Type m_storeType = StoreType::None;
    int m_eventId = -1;

    class LocalSink* m_sink = nullptr;
    class Subscription* m_subscription = nullptr;
};


#endif // _CFGCTXETW_HH_
