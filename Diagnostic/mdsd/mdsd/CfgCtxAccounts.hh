// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXACCOUNTS_HH_
#define _CFGCTXACCOUNTS_HH_

#include "CfgContext.hh"


class CfgCtxAccounts : public CfgContext
{
public:
	CfgCtxAccounts(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxAccounts() {}

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }
	CfgContext* Leave() override;

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

class CfgCtxAccount : public CfgContext
{
public:
	CfgCtxAccount(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxAccount() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

class CfgCtxSAS : public CfgContext
{
public:
	CfgCtxSAS(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxSAS() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXACCOUNTS_HH_
