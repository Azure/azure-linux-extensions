// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxSchemas.hh"
#include "MdsdConfig.hh"
#include "Engine.hh"
#include "TableSchema.hh"
#include <sstream>

subelementmap_t CfgCtxSchemas::_subelements = {
	{ "Schema", [](CfgContext* parent) -> CfgContext* { return new CfgCtxSchema(parent); } }
};

std::string CfgCtxSchemas::_name = "Schemas";

///////////////////////

subelementmap_t CfgCtxSchema::_subelements = {
	{ "Column", [](CfgContext* parent) -> CfgContext* { return new CfgCtxColumn(parent); } }
};

std::string CfgCtxSchema::_name = "Schema";

const subelementmap_t&
CfgCtxSchema::GetSubelementMap() const
{
	if (_schema) { return _subelements; }
	else { return CfgCtxError::subelements; }
}

void
CfgCtxSchema::Enter(const xmlattr_t& properties)
{
	_schema = 0;

	for (const auto& item : properties)
	{
		if (item.first == "name") {
			if (_schema == 0) {
				_schema = new TableSchema(item.second);
			}
			else {
				Config->AddMessage(MdsdConfig::error, "\"name\" can appear in <Schema> only once");
			}
		}
		else {
			Config->AddMessage(MdsdConfig::warning, "Ignoring unexpected attribute \"" + item.first + "\"");
		}
	}

	if (_schema == 0) {
		Config->AddMessage(MdsdConfig::fatal, "<Schema> requires \"name\" attribute");
	}
}

// Called from CfgCtxColumn::Enter()
void
CfgCtxSchema::AddColumn(const std::string& n, const std::string& srctype, const std::string& mdstype)
{
	// If we have no valid schema, or we've seen the column before, skip it.
	if (!_schema) return;

	auto result = _schema->AddColumn(n, srctype, mdstype);
	if (!result) {
		return;
	}

	std::ostringstream msg;
	switch (result) {
		case TableSchema::Ok:
			return;		// !!! Return, not break
		case TableSchema::NoConverter:
			msg << "Can't convert " << srctype << " to " << mdstype << " - ignoring column " << n;
			msg << ". Known converters: " << Engine::ListConverters();
			break;
		case TableSchema::DupeColumn:
			msg << "Column " << n << " already added to Schema " << _schema->Name();
			delete _schema;
			_schema = 0;		// Throw away the schema, we're broken
			break;
		case TableSchema::BadSrcType:
			msg << "Unknown source type " << srctype << " - ignoring column " << n;
			msg << ". Known converters: " << Engine::ListConverters();
			break;
		case TableSchema::BadMdsType:
			msg << "Unknown MDS type " << mdstype << " - ignoring column " << n;
			msg << ". Known converters: " << Engine::ListConverters();
			break;
	}
	Config->AddMessage(MdsdConfig::error, msg.str());
}

CfgContext*
CfgCtxSchema::Leave()
{
	if (_schema) {
		Config->AddSchema(_schema);		// All the way through without a fatal error - add it to the config
	}
	else {
		Config->AddMessage(MdsdConfig::error, "Schema dropped from active configuration due to errors");
	}
	return ParentContext;
}

///////////////////////

subelementmap_t CfgCtxColumn::_subelements;

std::string CfgCtxColumn::_name = "Column";

void
CfgCtxColumn::Enter(const xmlattr_t& properties)
{
	std::string colname;
	std::string srctype, mdstype;

	for (const auto& item : properties)
	{
		if (item.first == "name") {
			colname = item.second;
		}
		else if (item.first == "type") {
			srctype = item.second;
		}
		else if (item.first == "mdstype") {
			mdstype = item.second;
		}
		else {
			Config->AddMessage(MdsdConfig::warning, "Ignoring unexpected attribute \"" + item.first + "\"");
		}
	}
	if (colname.empty() || srctype.empty() || mdstype.empty()) {
		Config->AddMessage(MdsdConfig::error, "Missing required attributes (name, type, mdstype)");
	}
	else {
		CfgCtxSchema* ctxschema = dynamic_cast<CfgCtxSchema*>(ParentContext);
		if (ctxschema) {
			ctxschema->AddColumn(colname, srctype, mdstype);
		}
		else {
			Config->AddMessage(MdsdConfig::fatal,
					"Found <Column> in <" + ParentContext->Name() + ">; that can't happen");
		}
	}
}

// vim: se sw=8 : 
