// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXENVELOPE_HH_
#define _CFGCTXENVELOPE_HH_

#include "CfgContext.hh"

class LocalSink;

class CfgCtxEnvelope : public CfgContext
{
public:
	CfgCtxEnvelope(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxEnvelope() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

class CfgCtxEnvelopeField : public CfgContext
{
public:
	enum ValueSource { none, environment, agentIdent, configFile };

	CfgCtxEnvelopeField(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxEnvelopeField() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);
	virtual void HandleBody(const std::string& body);
	CfgContext* Leave();

	void SetFieldValueIfUnset(ValueSource, const std::string &);

private:
	std::string FieldName;
	std::string FieldValue;
	ValueSource Source;

	static subelementmap_t _subelements;
	static std::string _name;

};


class CfgCtxEnvelopeExtension : public CfgContext
{
public:
	CfgCtxEnvelopeExtension(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxEnvelopeExtension() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	std::string ExtensionName;

	static subelementmap_t _subelements;
	static std::string _name;

};

#endif //_CFGCTXENVELOPE_HH_

// vim: set tabstop=4 softtabstop=4 shiftwidth=4 noexpandtab :
