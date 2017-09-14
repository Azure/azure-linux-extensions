// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxEnvelope.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"

/////// CfgCtxEnvelope

subelementmap_t CfgCtxEnvelope::_subelements = {
	{ "Field", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEnvelopeField(parent); } },
	{ "Extension", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEnvelopeExtension(parent); } },
};

std::string CfgCtxEnvelope::_name = "EnvelopeSchema";


/////// CfgCtxEnvelopeField

subelementmap_t CfgCtxEnvelopeField::_subelements;

std::string CfgCtxEnvelopeField::_name = "Field";

void
CfgCtxEnvelopeField::SetFieldValueIfUnset(CfgCtxEnvelopeField::ValueSource source, const std::string & value)
{
	if (Source != ValueSource::none) {
		WARNING(std::string("Cannot specify multiple sources for this value; using '") + FieldValue + "'");
	} else {
		FieldValue = value;
		Source = source;
	}
}

void CfgCtxEnvelopeField::Enter(const xmlattr_t& properties)
{
	Source = ValueSource::none;

	for (const auto& item : properties)
	{
		if (item.first == "name") {
			FieldName = item.second;
		} else if (item.first == "envariable") {
			try {
				SetFieldValueIfUnset(ValueSource::environment, MdsdUtil::GetEnvironmentVariable(item.second));
			}
			catch (std::exception & ex) {
				WARNING(ex.what());
				SetFieldValueIfUnset(ValueSource::environment, std::string());
			}
		} else if (item.first == "useComputerName") {
			SetFieldValueIfUnset(ValueSource::agentIdent, Config->AgentIdentity());
		} else {
			ERROR("<Field> ignoring unexpected attribute " + item.first);
		}
	}

	if (FieldName.empty()) {
		ERROR("<Field> missing required 'name' attribute");
	}
}


void
CfgCtxEnvelopeField::HandleBody(const std::string& body)
{
	if (Source == ValueSource::environment || Source == ValueSource::agentIdent) {
		WARNING(std::string("Cannot specify multiple sources for this value; using '") + FieldValue + "'");
	} else {
		FieldValue += body;
		Source = ValueSource::configFile;
	}
}

CfgContext*
CfgCtxEnvelopeField::Leave()
{
	if (!FieldName.empty()) {
		if (Source == ValueSource::none) {
			WARNING("No value supplied for this column; using empty string");
		}
		Config->AddEnvelopeColumn(std::move(FieldName), std::move(FieldValue));
	}
	return ParentContext;
}

/////// CfgCtxEnvelopeExtension

subelementmap_t CfgCtxEnvelopeExtension::_subelements = {
	{ "Field", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEnvelopeField(parent); } },
};

std::string CfgCtxEnvelopeExtension::_name = "Extension";

void CfgCtxEnvelopeExtension::Enter(const xmlattr_t& properties)
{
	for (const auto& item : properties)
	{
		if (item.first == "name") {
			ExtensionName = item.second;
		} else {
			ERROR("<EnvelopeSchema> ignoring unexpected attribute " + item.first);
		}
	}

	if (ExtensionName.empty()) {
		ERROR("<Extension> missing required 'name' attribute");
	}
}

// vim: set tabstop=4 softtabstop=4 shiftwidth=4 noexpandtab :
