// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXROOT_HH_
#define _CFGCTXROOT_HH_

#include "CfgContext.hh"
#include "MdsdConfig.hh"
#include <map>
#include <functional>

class CfgCtxRoot :
	public CfgContext
{
public:
	/// <summary>
	/// The root context for a document. Tracks no information from prior context. Is neither entered
	/// nor left, in the sense of document parsing.
	CfgCtxRoot(MdsdConfig* config) : CfgContext(config) {}
	virtual ~CfgCtxRoot() {};

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { log_entry(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXROOT_HH_
