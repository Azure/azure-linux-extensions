// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXSOURCES_HH_
#define _CFGCTXSOURCES_HH_

#include "CfgContext.hh"

class CfgCtxSources : public CfgContext
{
public:
	CfgCtxSources(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxSources() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxSource : public CfgContext
{
public:
	CfgCtxSource(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxSource() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXSOURCES_HH_
