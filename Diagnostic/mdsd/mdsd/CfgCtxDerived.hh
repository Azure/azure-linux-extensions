// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXDERIVED_HH_
#define _CFGCTXDERIVED_HH_

#include "CfgContext.hh"
#include "DerivedEvent.hh"
#include "StoreType.hh"

class CfgCtxDerived : public CfgContext
{
public:
	CfgCtxDerived(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxDerived() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxDerivedEvent : public CfgContext
{
public:
	CfgCtxDerivedEvent(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxDerivedEvent() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const;

	void Enter(const xmlattr_t& properties);
	CfgContext* Leave();

	bool isOK() const { return _isOK; }
	bool isStoredLocally() const { return StoreType::Local == _storeType; }
	DerivedEvent * GetTask() const { return _task; }
	void SuppressSchemaGeneration() { _doSchemaGeneration = false; }

private:
	static subelementmap_t _subelements;
	static std::string _name;

	DerivedEvent *_task;
	bool _isOK;
	StoreType::Type _storeType;
	bool _doSchemaGeneration;
};

class CfgCtxLADQuery : public CfgContext
{
public:
	CfgCtxLADQuery(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxLADQuery() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXDERIVED_HH_
