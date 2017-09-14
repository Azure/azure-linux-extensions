// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXMONMGMT_HH_
#define _CFGCTXMONMGMT_HH_

#include "CfgContext.hh"

class CfgCtxMonMgmt : public CfgContext
{
public:
	CfgCtxMonMgmt(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxMonMgmt() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);
	CfgContext* Leave();

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXMONMGMT_HH_
