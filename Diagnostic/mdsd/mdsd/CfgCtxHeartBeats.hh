// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#include "CfgContext.hh"


class CfgCtxHeartBeats : public CfgContext
{
public:
	CfgCtxHeartBeats(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxHeartBeats() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxHeartBeat : public CfgContext
{
public:
	CfgCtxHeartBeat(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxHeartBeat() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { log_entry(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};
