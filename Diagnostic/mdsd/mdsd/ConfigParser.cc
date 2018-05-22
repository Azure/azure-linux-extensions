// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "ConfigParser.hh"

ConfigParser::~ConfigParser()
{
}


void
ConfigParser::OnStartElement(const std::string& name, const xmlattr_t& properties)
{
	currentContext = currentContext->SubContextFactory(name);
	currentContext->Enter(properties);
}

void
ConfigParser::OnEndElement(const std::string&)
{
	CfgContext* tmp = currentContext;
	currentContext = currentContext->Leave();
	delete tmp;
}


