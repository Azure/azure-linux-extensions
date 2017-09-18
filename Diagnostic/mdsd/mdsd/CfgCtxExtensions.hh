// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXEXTENSIONS_HH_
#define _CFGCTXEXTENSIONS_HH_

#include "CfgContext.hh"
#include "CfgCtxError.hh"
#include <map>

class MdsdExtension;

/// <summmary>
/// Extensions define all the monitoring agent's extensions.
/// </summary>
class CfgCtxExtensions : public CfgContext
{
public:
    CfgCtxExtensions(CfgContext *config) : CfgContext(config) {}
    virtual ~CfgCtxExtensions() { }

    virtual const std::string& Name() const { return _name; }
    static const std::string& XmlName() { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

/// <summmary>
/// Extension specifies one monitoring agent extension. The Name and CommandLine of an
/// extension are required. Other properperties are optional.
/// </summary>
class CfgCtxExtension : public CfgContext
{
public:
    CfgCtxExtension(CfgContext * config) : 
    CfgContext(config), 
    _extension(nullptr)
    {}

    virtual ~CfgCtxExtension() { }

    virtual const std::string& Name() const { return _name; }
    static const std::string& XmlName() { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const
    {
        return (_extension_name.empty())? (CfgCtxError::subelements) : (_subelements);
    }

    void Enter(const xmlattr_t& properties);
    CfgContext* Leave();
    MdsdExtension * GetExtension() const { return _extension; }
private:
    static subelementmap_t _subelements;
    static std::string _name;
    std::string _extension_name;
    MdsdExtension * _extension;
};

/// <summmary>
/// This specifies an extension's command line. It is required.
/// </summary>
class CfgCtxExtCmdLine : public CfgContext
{
public:
    CfgCtxExtCmdLine(CfgContext * config) : CfgContext(config) {}
    virtual ~CfgCtxExtCmdLine() { }

    virtual const std::string & Name() const { return _name; }
    static const std::string& XmlName() { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }
    CfgContext* Leave();

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

/// <summary>
/// Body: optional XML element. It specifies an extension's config body to be passed to the
/// extension via environment variable "MON_EXTENSION_BODY".
/// </summary>
class CfgCtxExtBody : public CfgContext
{
public:
    CfgCtxExtBody(CfgContext * config) : CfgContext(config) {}
    virtual ~CfgCtxExtBody() { }

    virtual const std::string & Name() const { return _name; }
    static const std::string& XmlName() { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }
    CfgContext* Leave();

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

/// <summmary>
/// This specifies the extension home directory. It is optional.
/// </summary>
class CfgCtxExtAlterLocation : public CfgContext
{
public:
    CfgCtxExtAlterLocation(CfgContext * config) : CfgContext(config) {}
    virtual ~CfgCtxExtAlterLocation() { }

    virtual const std::string & Name() const { return _name; }
    static const std::string& XmlName() { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }
    CfgContext* Leave();

private:
    static subelementmap_t _subelements;
    static std::string _name;
};

/// <summmary>
/// This specifies the limits of CPU, memory, IO throttling information. They will overwrite
/// the default values defined in Management\AgentResourceUsage\ExtensionResourceUsage.
/// </summary>
class CfgCtxExtResourceUsage : public CfgContext
{
public:
    CfgCtxExtResourceUsage(CfgContext * config) : CfgContext(config) { }
    virtual ~CfgCtxExtResourceUsage() { }

    virtual const std::string & Name() const { return _name; }
    static const std::string& XmlName() { return _name; }
    virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

    void Enter(const xmlattr_t& properties);

private:
    static subelementmap_t _subelements;
    static std::string _name;
};


#endif // _CFGCTXEXTENSIONS_HH_
