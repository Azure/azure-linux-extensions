// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXEVENTS_HH_
#define _CFGCTXEVENTS_HH_

#include "CfgContext.hh"

class CfgCtxEvents : public CfgContext
{
public:
	CfgCtxEvents(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxEvents() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXEVENTS_HH_
