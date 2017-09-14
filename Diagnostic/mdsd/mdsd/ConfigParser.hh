// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CONFIGPARSER_HH_
#define _CONFIGPARSER_HH_

#include "SaxParserBase.hh"
#include "CfgContext.hh"
#include "MdsdConfig.hh"
#include <list>

class ConfigParser : public SaxParserBase
{
public:
	/// <summary>
	/// Initialize a parser to handle a config file.
	/// </summary>
	/// <param name="Root">A CfgContext class whose factory can construct contexts for the expected root element</param>
	/// <param name="Config">The MdsdConfig to which this parse should log any warnings or errors</param>
	ConfigParser(CfgContext* Root, MdsdConfig* Config) : currentContext(Root), config(Config) {};

	virtual ~ConfigParser();

private:
	CfgContext* currentContext;
	MdsdConfig* const config;

protected:
	virtual void OnStartDocument() override {};
	virtual void OnEndDocument() override {};
	virtual void OnComment(const std::string&) override {};
	virtual void OnStartElement(const std::string& name, const xmlattr_t& properties) override;
	virtual void OnCharacters(const std::string& characters) override { currentContext->HandleBody(characters); };
	virtual void OnEndElement(const std::string& name) override;

	virtual void OnWarning(const std::string& text) override { config->AddMessage(MdsdConfig::warning, text); }
	virtual void OnError(const std::string& text) override { config->AddMessage(MdsdConfig::error, text); }
	virtual void OnFatalError(const std::string& text) override { config->AddMessage(MdsdConfig::fatal, text); }

	virtual void OnCDataBlock(const std::string& text) override { currentContext->HandleCdata(text); }
};
#endif //_CONFIGPARSER_HH_
