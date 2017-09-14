// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXIMPORTS_HH_
#define _CFGCTXIMPORTS_HH_

#include "CfgContext.hh"


class CfgCtxImports : public CfgContext
{
public:
	CfgCtxImports(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxImports() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }


private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxImport : public CfgContext
{
public:
	CfgCtxImport(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxImport() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXIMPORTS_HH_
