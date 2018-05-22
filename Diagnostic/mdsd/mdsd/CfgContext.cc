// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgContext.hh"
#include "CfgCtxError.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"

#include <sstream>

CfgContext*
CfgContext::SubContextFactory(const std::string& name)
{
	if (IsErrorContext()) {
		return new CfgCtxError(this);
	}

	const subelementmap_t& subelementmap = GetSubelementMap();
	auto iter = subelementmap.find(name);
	if (iter != subelementmap.end()) {
		return (iter->second)(this);
	} else {
		std::ostringstream oss;
		oss << '<' << Name() << "> does not define subelement <" << name << '>';
		ERROR(oss.str());
		return new CfgCtxError(this);
	}
}

std::string
CfgContext::stringize_attributes(const xmlattr_t& properties)
{
	std::string result;
	bool first = true;

	for (const auto& item : properties)
	{
		if (!first) {
			result += ", ";
		}
		result += item.first + "=\"" + item.second + "\"";
		first = false;
	}
	return result;
}

void
CfgContext::log_entry(const xmlattr_t& properties)
{
	std::string msg;
	if (properties.size() > 0) {
		msg = "Entered " + Name() + " with attribute(s) " + stringize_attributes(properties);
	}
	else {
		msg = "Entered " + Name();
	}
	INFO(msg);
}

void
CfgContext::log_body(const std::string& body)
{
	INFO("Element " + Name() + " has body {" + body + "}");
}

bool
CfgContext::empty_or_whitespace()
{
	return MdsdUtil::IsEmptyOrWhiteSpace(Body);
}

CfgContext* CfgContext::Leave() {
	if (!empty_or_whitespace()) {
		std::ostringstream oss;
		oss << '<' << Name() << "> expected empty body; did not expect {" << Body << '}';
		WARNING(oss.str());
	}
	return ParentContext;
}

void CfgContext::warn_if_attributes(const xmlattr_t& properties)
{
	// log_entry(properties);

	if (!properties.empty()) {
		WARNING("Expected no attributes");
	}
}

void
CfgContext::INFO(const std::string& msg) { Config->AddMessage(MdsdConfig::info, msg); }

void
CfgContext::WARNING(const std::string& msg) { Config->AddMessage(MdsdConfig::warning, msg); }

void
CfgContext::ERROR(const std::string& msg) { Config->AddMessage(MdsdConfig::error, msg); }

void
CfgContext::FATAL(const std::string& msg) { Config->AddMessage(MdsdConfig::fatal, msg); }

void
CfgContext::parse_singleton_attribute(
	const std::string & itemname,
	const std::string & itemval,
	const std::string & attrname,
	std::string& attrval
	)
{
	if (attrname != itemname) {
		return;
	}
	if (attrval.empty()) {
		attrval = itemval;
	}
	else {
		ERROR("\"" + attrname + "\" can appear in <" + Name() + "> only once.");
	}
}

void
CfgContext::fatal_if_no_attributes(
	const std::string & attrname,
	const std::string & attrval
	)
{
	if (attrval.empty()) {
		FATAL("<" + Name() + "> requires \"" + attrname + "\" attribute.");
	}
}

// vim: se sw=8 :
