// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxRoot.hh"
#include "CfgCtxMonMgmt.hh"

subelementmap_t CfgCtxRoot::_subelements = {
	{ "MonitoringManagement", [](CfgContext* parent) -> CfgContext* { return new CfgCtxMonMgmt(parent); } }
};

std::string CfgCtxRoot::_name = "(Document Root)";
