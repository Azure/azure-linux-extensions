// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxEventAnnotations.hh"
#include "MdsdConfig.hh"
#include "ConfigParser.hh"
#include "MdsTime.hh"
#include "Trace.hh"
#include "CfgOboDirectConfig.hh"
#include "MdsdEventCfg.hh"
#include "EventPubCfg.hh"
#include "Utility.hh"
#include "cryptutil.hh"

///////// CfgCtxEventAnnotations

subelementmap_t CfgCtxEventAnnotations::_subelements = {
    { "EventStreamingAnnotation", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEventAnnotation(parent); } }
};

std::string CfgCtxEventAnnotations::_name = "EventStreamingAnnotations";

void
CfgCtxEventAnnotations::SetEventType(
    const std::string & itemname,
    EventAnnotationType::Type type
    )
{
    if (itemname.empty()) {
        ERROR("<" + Name() + "> invalid empty itemname attribute");
        return;
    }

    // if duplicate, report error
    auto item = _eventmap.find(itemname);
    if (item != _eventmap.end()) {
        if (item->second & type) {
            ERROR("<" + Name() + "> itemname " + itemname + " already defined for type " + std::to_string(type));
        }
    }

    _eventmap[itemname] = static_cast< EventAnnotationType::Type>(_eventmap[itemname] | type);
}

CfgContext*
CfgCtxEventAnnotations::Leave()
{
    if (_eventmap.size() > 0) {
        Config->GetMdsdEventCfg()->SetEventAnnotationTypes(std::move(_eventmap));
    }
    return ParentContext;
}

///////// CfgCtxEventAnnotation

subelementmap_t CfgCtxEventAnnotation::_subelements = {
    { "EventPublisher", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEPA(parent); } },
    { "OnBehalf", [](CfgContext* parent) -> CfgContext* {
        return new CfgCtxOnBehalf(parent, dynamic_cast<CfgCtxEventAnnotation*>(parent)->_itemName); }
    }
};

std::string CfgCtxEventAnnotation::_name = "EventStreamingAnnotation";


void
CfgCtxEventAnnotation::Enter(const xmlattr_t& properties)
{
    const std::string attrName = "name";

    for (const auto & item : properties) {
        if (attrName ==  item.first) {
            parse_singleton_attribute(item.first, item.second, attrName, _itemName);
        }
        else {
            warn_if_attribute_unexpected(item.first);
        }
    }
    fatal_if_no_attributes(attrName, _itemName);
}

void
CfgCtxEventAnnotation::SetEventType(EventAnnotationType::Type eventType)
{
    auto parentObj = dynamic_cast<CfgCtxEventAnnotations*>(ParentContext);
    if (!parentObj) {
        fatal_if_impossible_subelement();
        return;
    }

    parentObj->SetEventType(_itemName, eventType);
}

void
CfgCtxEventAnnotation::SetEventSasKey(
    std::string&& saskey
    )
{
    if (saskey.empty()) {
        return;
    }

    // EventHubs publisher requires resourceId defined for Shoebox V2.
    // If another scenario needs to be supported, this code may need to be changed as well.
    if (Config->GetResourceId().empty()) {
        ERROR("<" + Name() + ">: OboDirectPartitionField resourceId is missing, when Shoebox V2 EventHubs publisher needs one.");
        return;
    }

    try {
        Config->GetEventPubCfg()->AddAnnotationKey(_itemName, std::move(saskey));
    }
    catch(const std::exception& ex) {
        ERROR("<" + Name() + "> exception: " + ex.what());
    }
}

///////// CfgCtxEPA

subelementmap_t CfgCtxEPA::_subelements = {
    { "Content", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEPAContent(parent); } },
    { "Key", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEPAKey(parent); } }
};

void
CfgCtxEPA::Enter(const xmlattr_t& properties)
{
    warn_if_attributes(properties);

    // Set the event type (EventPublisher) for the event (this Publisher element's parent's name attribute) in the EventAnnotations (grandparent) element's event type map
    auto parentObj = dynamic_cast<CfgCtxEventAnnotation*>(ParentContext);
    if (!parentObj)
    {
        fatal_if_impossible_subelement();
        return;
    }
    parentObj->SetEventType(EventAnnotationType::Type::EventPublisher);
}

void
CfgCtxEPA::SetEventSasKey(
    std::string&& saskey
    )
{
    if (saskey.empty()) {
        return;
    }

    auto parentObj = dynamic_cast<CfgCtxEventAnnotation*>(ParentContext);
    if (!parentObj)
    {
        fatal_if_impossible_subelement();
        return;
    }
    parentObj->SetEventSasKey(std::move(saskey));
}

std::string CfgCtxEPA::_name = "EventPublisher";

///////// CfgCtxEPAContent

subelementmap_t CfgCtxEPAContent::_subelements;
std::string CfgCtxEPAContent::_name = "Content";


///////// CfgCtxEPAKey

subelementmap_t CfgCtxEPAKey::_subelements;
std::string CfgCtxEPAKey::_name = "Key";

void
CfgCtxEPAKey::Enter(const xmlattr_t& properties)
{
    // Decrypt key path attribute is optional
    const std::string & decryptKeyPathAttr = "decryptKeyPath";

    for (const auto & item : properties) {
        if (decryptKeyPathAttr == item.first) {
            parse_singleton_attribute(item.first, item.second, decryptKeyPathAttr, _decryptKeyPath);
        }
        else {
            warn_if_attribute_unexpected(item.first);
        }
    }
}


CfgContext*
CfgCtxEPAKey::Leave()
{
    if (Body.empty()) {
        return ParentContext;
    }

    auto parentObj = dynamic_cast<CfgCtxEPA*>(ParentContext);
    if (!parentObj)
    {
        fatal_if_impossible_subelement();
        return ParentContext;
    }

    if (_decryptKeyPath.empty()) {
        auto escapedConnStr = MdsdUtil::UnquoteXmlAttribute(Body);
        parentObj->SetEventSasKey(std::move(escapedConnStr));
    }
    else {
        if (!MdsdUtil::IsRegFileExists(_decryptKeyPath)) {
            ERROR("Cannot find decrypt key path " + _decryptKeyPath);
        }
        else {
            try {
                auto decryptedSas = cryptutil::DecodeAndDecryptString(_decryptKeyPath, Body);
                parentObj->SetEventSasKey(std::move(decryptedSas));
            }
            catch(const std::exception & ex) {
                ERROR("EventPublisher SAS key decryption using private key file '" +
                    _decryptKeyPath + "' failed: " + ex.what());
            }
        }
    }

    return ParentContext;
}


/////////// CfgCtxOnBehalf

subelementmap_t CfgCtxOnBehalf::_subelements = {
        { "Content", [](CfgContext* parent) -> CfgContext* { return new CfgCtxOnBehalfContent(parent, dynamic_cast<CfgCtxOnBehalf*>(parent)->_eventName); } }
};

std::string CfgCtxOnBehalf::_name = "OnBehalf";

void
CfgCtxOnBehalf::Enter(const xmlattr_t& properties)
{
    std::string valDirectMode;
    const std::string attrDirectMode = "directMode";

    for (const auto& item : properties)
    {
        if (attrDirectMode == item.first)
        {
            parse_singleton_attribute(item.first, item.second, attrDirectMode, valDirectMode);
        }
        else
        {
            warn_if_attribute_unexpected(item.first);
        }
    }
    fatal_if_no_attributes(attrDirectMode, valDirectMode);

    if (valDirectMode != "true")
    {
        ERROR("<" + Name() + "> supports attribute " + attrDirectMode + "=\"true\" only currently");
    }

    // Set the event type (OnBehalf) for the event (this Publisher element's parent's name attribute) in the EventAnnotations (grandparent) element's event type map
    auto parentObj = dynamic_cast<CfgCtxEventAnnotation*>(ParentContext);
    if (!parentObj)
    {
        fatal_if_impossible_subelement();
        return;
    }
    parentObj->SetEventType(EventAnnotationType::Type::OnBehalf);
}

/////////// CfgCtxOnBehalfContent

subelementmap_t CfgCtxOnBehalfContent::_subelements = {
        { "Config", [](CfgContext* parent) -> CfgContext* { return new CfgCtxOnBehalfConfig(parent, dynamic_cast<CfgCtxOnBehalfContent*>(parent)->_eventName); } }    // This is a trick to handle the CDATA XML content as a subelement...
};

std::string CfgCtxOnBehalfContent::_name = "Content";

void
CfgCtxOnBehalfContent::Enter(const xmlattr_t& properties)
{
    warn_if_attributes(properties);
}

CfgContext*
CfgCtxOnBehalfContent::Leave()
{
    if (Body.empty())
    {
        ERROR("<" + Name() +"> must have a body (CDATA), but it's empty");
    }
    else
    {
        // Trick: Parse the cdata (another XML) by treating it as a subelement...
        ConfigParser xmlCdataParser(this, Config);
        xmlCdataParser.Parse(Body);
    }
    return ParentContext;
}

///////////// CfgCtxOnBehalfConfig (XML in CDATA of CfgCtxOnBehalfContent...)

subelementmap_t CfgCtxOnBehalfConfig::_subelements;

std::string CfgCtxOnBehalfConfig::_name = "Config";

void
CfgCtxOnBehalfConfig::Enter(const xmlattr_t& properties)
{
    Trace trace(Trace::ConfigLoad, "CfgCtxOnBehalfConfig::Enter");

    auto oboDirectConfig = std::make_shared<mdsd::OboDirectConfig>();

    for (const auto& item : properties)
    {
        if (item.first == "onBehalfFields") // Not used by mdsd yet
        {
            oboDirectConfig->onBehalfFields = item.second;
        }
        else if (item.first == "containerSuffix") // Not used by mdsd yet
        {
            oboDirectConfig->containerSuffix = item.second;
        }
        else if (item.first == "primaryPartitionField")
        {
            oboDirectConfig->primaryPartitionField = item.second;
        }
        else if (item.first == "partitionFields")
        {
            oboDirectConfig->partitionFields = item.second;
        }
        else if (item.first == "onBehalfReplaceFields") // Not used by mdsd yet
        {
            oboDirectConfig->onBehalfReplaceFields = item.second;
        }
        else if (item.first == "excludeFields") // Not used by mdsd yet
        {
            oboDirectConfig->excludeFields = item.second;
        }
        else if (item.first == "timePeriods")
        {
            if (MdsTime::FromIS8601Duration(item.second).to_time_t() == 0)
            {
                ERROR("Invalid ISO8601 time duration is given: " + item.second);
            }
            else
            {
                oboDirectConfig->timePeriods = item.second;
            }
        }
        else if (item.first == "priority")
        {
            oboDirectConfig->priority = item.second;
        }
        else
        {
            warn_if_attribute_unexpected(item.first);
        }
    }

    Config->AddOboDirectConfig(_eventName, std::move(oboDirectConfig));
}
