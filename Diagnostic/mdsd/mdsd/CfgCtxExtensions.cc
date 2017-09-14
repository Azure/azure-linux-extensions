// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxExtensions.hh"
#include "Utility.hh"
#include "MdsdExtension.hh"
#include "MdsdConfig.hh"
#include "CmdLineConverter.hh"

////////////////// CfgCtxExtensions

subelementmap_t CfgCtxExtensions::_subelements = {
    { "Extension", [] (CfgContext* parent) -> CfgContext* { return new CfgCtxExtension(parent); } }
};

std::string CfgCtxExtensions::_name = "Extensions";

////////////////// CfgCtxExtension

void
CfgCtxExtension::Enter(const xmlattr_t& properties)
{
    const std::string extNameAttr = "extensionName";

    for (const auto & item : properties) {
        if (extNameAttr == item.first)
        {
            _extension_name = item.second;
        }
        else  {
            WARNING("Ignoring unexpected attribute " + item.second);
        }
    }
    
    if (_extension_name.empty())
    {
        ERROR("<" + _name + "> requires attribute '" + extNameAttr + "'");
    }

    _extension = new MdsdExtension(_extension_name);
}

CfgContext* CfgCtxExtension::Leave()
{
    if (_extension)
    {
        Config->AddExtension(_extension);
    }
    else {
        ERROR("Unexpected NULL value for MdsdExtension object in CfgCtxExtension.");
    }
    return ParentContext;
}


subelementmap_t CfgCtxExtension::_subelements = {
    { "CommandLine", [] (CfgContext* parent) -> CfgContext* { return new CfgCtxExtCmdLine(parent); } },
    { "Body", [] (CfgContext* parent) -> CfgContext* { return new CfgCtxExtBody(parent); } },
    { "AlternativeExtensionLocation", [] (CfgContext* parent) -> CfgContext* { return new CfgCtxExtAlterLocation(parent); } },
    { "ResourceUsage", [] (CfgContext* parent) -> CfgContext* { return new CfgCtxExtResourceUsage(parent); } }
};

std::string CfgCtxExtension::_name = "Extension";


////////////////// CfgCtxExtCmdLine

CfgContext* CfgCtxExtCmdLine::Leave()
{
    std::string cmdline = std::move(Body);

    if (MdsdUtil::IsEmptyOrWhiteSpace(cmdline))
    {
        ERROR("unexpected empty or whitespace value for Extension CmdLine");
    }
    else
    {
        CfgCtxExtension * ctxext = dynamic_cast<CfgCtxExtension*>(ParentContext);
        if (ctxext)
        {
            CmdLineConverter::Tokenize(cmdline, std::bind(&CfgContext::WARNING, this, std::placeholders::_1));	// To warn (if any) sooner than later
            ctxext->GetExtension()->SetCmdLine(cmdline);
        }
        else {
            FATAL("Found <" + _name + "> in <" + ParentContext->Name() + ">; that can't happen");
        }
    }

    return ParentContext;
}

subelementmap_t CfgCtxExtCmdLine::_subelements;
std::string CfgCtxExtCmdLine::_name = "CommandLine";

////////////////// CfgCtxExtBody

CfgContext* CfgCtxExtBody::Leave()
{
    if (empty_or_whitespace())
    {
        WARNING("<" + _name + "> expected non-empty body; did not expect '{" + Body + "}'");
    }
    else
    {
        CfgCtxExtension * ctxext = dynamic_cast<CfgCtxExtension*>(ParentContext);
        if (ctxext)
        {
            ctxext->GetExtension()->SetBody(Body);
        }
        else {
            FATAL("Found <" + _name + "> in <" + ParentContext->Name() + ">; that can't happen");
        }
    }

    return ParentContext;
}

subelementmap_t CfgCtxExtBody::_subelements;
std::string CfgCtxExtBody::_name = "Body";


////////////////// CfgCtxExtAlterLocation

CfgContext* CfgCtxExtAlterLocation::Leave()
{
    std::string loc = std::move(Body);
    if (MdsdUtil::IsEmptyOrWhiteSpace(loc))
    {
        WARNING("<" + _name + "> value cannot be empty or whitespace.");
    }
    else
    {
        CfgCtxExtension * ctxext = dynamic_cast<CfgCtxExtension*>(ParentContext);
        if (ctxext)
        {
            ctxext->GetExtension()->SetAlterLocation(loc);
        }
        else {
            FATAL("Found <" + _name + "> in <" + ParentContext->Name() + ">; that can't happen");
        }
    }

    return ParentContext;
}

subelementmap_t CfgCtxExtAlterLocation::_subelements;
std::string CfgCtxExtAlterLocation::_name = "AlternativeExtensionLocation";

////////////////// CfgCtxExtResourceUsage

void 
CfgCtxExtResourceUsage::Enter(const xmlattr_t& properties)
{
    CfgCtxExtension * ctxext = dynamic_cast<CfgCtxExtension*>(ParentContext);
    if (!ctxext) {
        FATAL("Found <" + _name + "> in <" + ParentContext->Name() + ">; that can't happen");
        return;
    }

    MdsdExtension * ext = ctxext->GetExtension();

    for (const auto & item : properties) {
        if ("cpuPercentUsage" == item.first)
        {
            float f = std::stof(item.second);
            ext->SetCpuPercentUsage(f);
        }
        else if ("cpuThrottling" == item.first)
        {
            bool b = MdsdUtil::to_bool(item.second);
            ext->SetIsCpuThrottling(b);
        }
        else if ("memoryLimitInMB" == item.first)
        {
            unsigned long long m = std::stoull(item.second);
            ext->SetMemoryLimitInMB(m);
        }
        else if ("memoryThrottling" == item.first)
        {
            bool b = MdsdUtil::to_bool(item.second);
            ext->SetIsMemoryThrottling(b);
        }
        else if ("ioReadLimitInKBPerSecond" == item.first)
        {
            unsigned long long n = std::stoull(item.second);
            ext->SetIOReadLimitInKBPerSecond(n);
        }
        else if ("ioReadThrottling" == item.first)
        {
            bool b = MdsdUtil::to_bool(item.second);
            ext->SetIsIOReadThrottling(b);
        }
        else if ("ioWriteLimitInKBPerSecond" == item.first)
        {
            unsigned long long n = std::stoull(item.second);
            ext->SetIOWriteLimitInKBPerSecond(n);
        }
        else if ("ioWriteThrottling" == item.first)
        {
            bool b = MdsdUtil::to_bool(item.second);
            ext->SetIsIOWriteThrottling(b);
        }
        else
        {
            WARNING("Ignoring unexpected attribute " + item.second);
        }
    }
}

subelementmap_t CfgCtxExtResourceUsage::_subelements;
std::string CfgCtxExtResourceUsage::_name = "ResourceUsage";

