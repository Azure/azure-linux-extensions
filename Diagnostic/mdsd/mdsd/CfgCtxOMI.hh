// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXOMI_HH_
#define _CFGCTXOMI_HH_

#include "CfgContext.hh"
#include "StoreType.hh"
#include <unordered_map>
#include "PipeStages.hh"

class OmiTask;

class CfgCtxOMI : public CfgContext
{
public:
	CfgCtxOMI(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxOMI() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxOMIQuery : public CfgContext
{
public:
	CfgCtxOMIQuery(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxOMIQuery() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const;

	void Enter(const xmlattr_t& properties);
	CfgContext* Leave();

	OmiTask * GetTask() const { return _task; }
	bool isOK() const { return _isOK; }

private:
	static subelementmap_t _subelements;
	static std::string _name;
	OmiTask *_task;
	bool _isOK;
	StoreType::Type _storeType;
	bool _doSchemaGeneration;
};

class CfgCtxUnpivot : public CfgContext
{
public:
	CfgCtxUnpivot(CfgContext* config) : CfgContext(config), _isOK(true) {}
	virtual ~CfgCtxUnpivot() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);
	CfgContext* Leave();

	void addTransform(const std::string& from, const std::string& to, double scale = 1.0 );

private:
	static subelementmap_t _subelements;
	static std::string _name;

	CfgCtxOMIQuery* _query;
	bool _isOK;
	std::string _valueAttrName;
	std::string _nameAttrName;
	std::string _unpivotColumns;
	std::unordered_map<std::string, ColumnTransform> _transforms;
};

class CfgCtxMapName : public CfgContext
{
public:
	CfgCtxMapName(CfgContext* config) : CfgContext(config), _isOK(true), _scale(1.0) {}
	virtual ~CfgCtxMapName() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);
	void HandleBody(const std::string& body);
	CfgContext* Leave();

private:
	static subelementmap_t _subelements;
	static std::string _name;

	bool _isOK;
	CfgCtxUnpivot* _unpivot;
	std::string _from;
	std::string _to;
	double _scale;
};

#endif //_CFGCTXOMI_HH_

// vim: se sw=8 :
