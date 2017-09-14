// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXEVENTANNOTATIONS_HH_
#define _CFGCTXEVENTANNOTATIONS_HH_

#include "CfgContext.hh"
#include "CfgEventAnnotationType.hh"
#include <unordered_map>

class CfgCtxEventAnnotations : public CfgContext
{
public:
    CfgCtxEventAnnotations(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxEventAnnotations() {}

    virtual const std::string & Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }
    CfgContext* Leave();

    /// Set each annotation name and type.
    /// The itemname can be event name, source name, etc.
    void SetEventType(const std::string & itemname, EventAnnotationType::Type type);

private:
    static subelementmap_t _subelements;
    static std::string _name;

    /// map key: itemname, value: annotation type
    std::unordered_map<std::string, EventAnnotationType::Type> _eventmap;
};

class CfgCtxEventAnnotation : public CfgContext
{
public:
    CfgCtxEventAnnotation(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxEventAnnotation() {}

    virtual const std::string & Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties);

    void SetEventType(EventAnnotationType::Type type);
    void SetEventSasKey(std::string&& saskey);

private:
    static subelementmap_t _subelements;
    static std::string _name;

    std::string _itemName;
};

class CfgCtxEPA : public CfgContext
{
public:
    CfgCtxEPA(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxEPA() {}

    virtual const std::string & Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties);
    void SetEventSasKey(std::string&& saskey);

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

class CfgCtxEPAContent : public CfgContext
{
public:
    CfgCtxEPAContent(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxEPAContent() {}

    virtual const std::string & Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

class CfgCtxEPAKey : public CfgContext
{
public:
    CfgCtxEPAKey(CfgContext* config) : CfgContext(config) {}
    virtual ~CfgCtxEPAKey() {}
    virtual const std::string & Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties);
    CfgContext* Leave();

private:
    static subelementmap_t _subelements;
    static std::string _name;
    std::string _decryptKeyPath;
};



class CfgCtxOnBehalf : public CfgContext
{
public:
    CfgCtxOnBehalf(CfgContext* config, const std::string& eventName)
        : CfgContext(config), _eventName(eventName)
    {}
    virtual ~CfgCtxOnBehalf() {}

    virtual const std::string& Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties);

private:
    static std::string _name;
    static subelementmap_t _subelements;

    std::string _eventName;
};

class CfgCtxOnBehalfContent : public CfgContext
{
public:
    CfgCtxOnBehalfContent(CfgContext* config, const std::string& eventName)
        : CfgContext(config), _eventName(eventName)
    {}
    virtual ~CfgCtxOnBehalfContent() {}

    virtual const std::string& Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties);
    CfgContext* Leave();

private:
    static std::string _name;
    static subelementmap_t _subelements;

    std::string _eventName;
};

class CfgCtxOnBehalfConfig : public CfgContext
{
public:
    CfgCtxOnBehalfConfig(CfgContext* config, const std::string& eventName)
        : CfgContext(config), _eventName(eventName)
    {}
    virtual ~CfgCtxOnBehalfConfig() {}

    virtual const std::string& Name() const { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }
    void Enter(const xmlattr_t& properties);

private:
    static std::string _name;
    static subelementmap_t _subelements;

    std::string _eventName;
};

#endif // _CFGCTXEVENTANNOTATIONS_HH_
