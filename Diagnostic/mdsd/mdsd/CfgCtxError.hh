// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef _CFGCTXERROR_HH_
#define _CFGCTXERROR_HH_

#include "CfgContext.hh"

/// <summary>
/// Once an unexpected element is found while parsing the config file, this class sets up
/// an "error detected" context that is propagated until the parse leaves the unexpected
/// element. Note that any Insert elements are ignored by this context.
/// </summary>
class CfgCtxError :
	public CfgContext
{
public:
	CfgCtxError(CfgContext* previousContext) : CfgContext(previousContext) {}
	virtual ~CfgCtxError() { }

	virtual const std::string& Name() const { return name; }
	const subelementmap_t& GetSubelementMap() const { return subelements; }

	// We're deliberately silent on the attributes and body of elements while we're in an error state
	void Enter(const xmlattr_t&) {};
	void HandleBody(const std::string&) {};
	CfgContext* Leave() { return ParentContext; }

	/// <summary>
	/// An empty list of legal subelements. Any context can return this from GetSubelementMap() if the
	/// element has errors that block usage.
	/// </summary>
	static subelementmap_t subelements;

	/// <summary>True if the parse is in "error" state</summary>
	virtual bool IsErrorContext() const { return true; }

private:
	static std::string name;
};

#endif //_CFGCTXERROR_HH_

// vim: se sw=8 :
