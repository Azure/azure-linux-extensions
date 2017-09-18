// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxSources.hh"
#include "MdsdConfig.hh"
#include "LocalSink.hh"
#include "EventType.hh"
#include "Utility.hh"

subelementmap_t CfgCtxSources::_subelements = {
	{ "Source", [](CfgContext* parent) -> CfgContext* { return new CfgCtxSource(parent); } }
};

std::string CfgCtxSources::_name = "Sources";

////////////

void
CfgCtxSource::Enter(const xmlattr_t& properties)
{
    std::string name, schema, dynamic_schema;

    for (const auto& item : properties)
    {
        if (item.first == "name") {
            name = item.second;
        }
        else if (item.first == "schema") {
            schema = item.second;
        }
        else if (item.first == "dynamic_schema") {
            dynamic_schema = item.second;
        }
        else {
            Config->AddMessage(MdsdConfig::warning, "Ignoring unexpected attribute \"" + item.first + "\"");
        }
    }

    auto isOK = true;
    if (name.empty()) {
        Config->AddMessage(MdsdConfig::fatal, "<Source> requires a \"name\" attribute");
        isOK = false;
    }

    auto isDynamicSchema = MdsdUtil::to_bool(dynamic_schema);

    if ((!schema.empty() && isDynamicSchema) ||
        (schema.empty() && (dynamic_schema.empty() || !isDynamicSchema))) {
        Config->AddMessage(MdsdConfig::fatal, "<Source> requires either a valid \"schema\" attribute or that the \"dynamic_schema\" attribute be set to \"true\", but not both.");
    }

    if (!isOK) {
        return;
    }

    auto sink = LocalSink::Lookup(name);
    if (!sink) {
        sink = new LocalSink(name);
    }

    if (!isDynamicSchema) {
        Config->AddSource(name, schema);
        sink->AllocateSchemaId();
    }
    else {
        Config->AddDynamicSchemaSource(name);
    }

    Config->AddMonikerEventInfo("", "", StoreType::Local, name, mdsd::EventType::None);
}

subelementmap_t CfgCtxSource::_subelements;

std::string CfgCtxSource::_name = "Source";
