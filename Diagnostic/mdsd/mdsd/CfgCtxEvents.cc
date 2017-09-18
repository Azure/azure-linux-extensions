// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxEvents.hh"
#include "CfgCtxHeartBeats.hh"
#include "CfgCtxOMI.hh"
#include "CfgCtxMdsdEvents.hh"
#include "CfgCtxDerived.hh"
#include "CfgCtxExtensions.hh"
#include "CfgCtxEtw.hh"

////////////////// CfgCtxEvents

subelementmap_t CfgCtxEvents::_subelements = {
	{ "HeartBeats", [](CfgContext* parent) -> CfgContext* { return new CfgCtxHeartBeats(parent); } },
	{ "OMI", [](CfgContext* parent) -> CfgContext* { return new CfgCtxOMI(parent); } },
	{ "MdsdEvents", [](CfgContext* parent) -> CfgContext* { return new CfgCtxMdsdEvents(parent); } },
	{ "DerivedEvents", [](CfgContext* parent) -> CfgContext* { return new CfgCtxDerived(parent); } },
	{ "Extensions", [](CfgContext* parent) -> CfgContext* { return new CfgCtxExtensions(parent); } },
	{ "EtwProviders", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEtwProviders(parent); } }
};

std::string CfgCtxEvents::_name = "Events";
