// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxImports.hh"
#include "MdsdConfig.hh"

////////////// CfgCtxImports

subelementmap_t CfgCtxImports::_subelements = {
	{ "Import", [](CfgContext* parent) -> CfgContext* { return new CfgCtxImport(parent); } }
};

std::string CfgCtxImports::_name = "Imports";

////////////// CfgCtxImport

subelementmap_t CfgCtxImport::_subelements;

std::string CfgCtxImport::_name = "Import";

void
CfgCtxImport::Enter(const xmlattr_t& properties)
{
	std::string filename;

	// Find the file attribute; invoke Config->LoadFromConfigFile() on the value thereof.
	for (const auto& item : properties)
	{
		if (item.first == "file") {
			filename = item.second;
		}
		else {
			Config->AddMessage(MdsdConfig::warning, "Ignoring unknown attribute \"" + item.first + "\"");
		}
	}
	if (filename.empty()) {
		Config->AddMessage(MdsdConfig::error, "<Import>:  \"file\" attribute is missing or empty");
	}
	else {
		Config->LoadFromConfigFile(filename);
	}
}
