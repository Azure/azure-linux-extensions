// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXSVCBUSACCTS_HH_
#define _CFGCTXSVCBUSACCTS_HH_

#include "CfgContext.hh"

class CfgCtxSvcBusAccts : public CfgContext
{
public:
    CfgCtxSvcBusAccts(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxSvcBusAccts() {}

    virtual const std::string & Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

class CfgCtxSvcBusAcct : public CfgContext
{
public:
    CfgCtxSvcBusAcct(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxSvcBusAcct() {}
    virtual const std::string& Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties);

    std::string GetMoniker() const { return _moniker; }
private:
    static subelementmap_t _subelements;
    static std::string _name;
    std::string _moniker;
};

class CfgCtxEventPublisher : public CfgContext
{
public:
    CfgCtxEventPublisher(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxEventPublisher() {}
    virtual const std::string& Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties);

private:
    static subelementmap_t _subelements;
    static std::string _name;
};


#endif // _CFGCTXSVCBUSACCTS_HH_
