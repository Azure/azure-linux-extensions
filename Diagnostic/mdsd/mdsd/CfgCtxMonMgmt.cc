// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxMonMgmt.hh"
#include "CfgCtxImports.hh"
#include "CfgCtxAccounts.hh"
#include "CfgCtxManagement.hh"
#include "CfgCtxSchemas.hh"
#include "CfgCtxEnvelope.hh"
#include "CfgCtxSources.hh"
#include "CfgCtxEvents.hh"
#include "CfgCtxSvcBusAccts.hh"
#include "CfgCtxEventAnnotations.hh"
#include "MdsdConfig.hh"
#include "Trace.hh"

subelementmap_t CfgCtxMonMgmt::_subelements = {
	{ "Imports",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxImports(parent); } },
	{ "Accounts",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxAccounts(parent); } },
	{ "Management",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxManagement(parent); } },
	{ "Schemas",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxSchemas(parent); } },
	{ "EnvelopeSchema",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxEnvelope(parent); } },
	{ "Sources",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxSources(parent); } },
	{ "Events",	[](CfgContext* parent) -> CfgContext* { return new CfgCtxEvents(parent); } },
	{ "ServiceBusAccountInfos", [](CfgContext* parent) -> CfgContext* { return new CfgCtxSvcBusAccts(parent); } },
	{ "EventStreamingAnnotations", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEventAnnotations(parent); } }
};

std::string CfgCtxMonMgmt::_name = "MonitoringManagement";

void
CfgCtxMonMgmt::Enter(const xmlattr_t& properties)
{
	Trace trace(Trace::ConfigLoad, "CfgCtxMonMgmt::Enter");
	if (Config->MonitoringManagementSeen()) {
		return;
	}

	bool versionChecked = false;

	for (const auto& item : properties)
	{
		if (item.first == "namespace") {
			Config->Namespace(item.second);
		}
		else if (item.first == "eventVersion") {
			int ver = std::stoi(item.second);
			if (ver > 0) {
				Config->EventVersion(ver);
			}
			else {
				Config->AddMessage(MdsdConfig::error, "eventVersion, when present, must be a positive integer");
			}
		}
		else if (item.first == "version") {
			versionChecked = true;
			if (item.second != "1.0") {
				Config->AddMessage(MdsdConfig::fatal, "Only config file version 1.0 is supported");
			}
		}
		else if (item.first == "timestamp") {
			Config->Timestamp(item.second);
		}
		else {
			Config->AddMessage(MdsdConfig::warning,
				"<MonitoringManagement> ignoring unexpected attribute \"" + item.first + "\"");
		}
	}
	if (!versionChecked) {
		Config->AddMessage(MdsdConfig::fatal, "Must specify \"version\" attribute");
	}

	Config->MonitoringManagementSeen(true);
}

CfgContext*
CfgCtxMonMgmt::Leave()
{
	Config->ValidateEvents();
	return ParentContext;
}

// vim: se sw=8 :
