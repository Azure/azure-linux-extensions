// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXSCHEMAS_HH_
#define _CFGCTXSCHEMAS_HH_

#include "CfgContext.hh"
#include "CfgCtxError.hh"
#include <set>

class TableSchema;

class CfgCtxSchemas : public CfgContext
{
public:
	CfgCtxSchemas(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxSchemas() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxSchema : public CfgContext
{
public:
	CfgCtxSchema(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxSchema() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const;

	void Enter(const xmlattr_t& properties);
	CfgContext* Leave();

	void AddColumn(const std::string& n, const std::string& srctype, const std::string& mdstype);

private:
	TableSchema* _schema;
	std::set<std::string> _columnNames;

	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxColumn : public CfgContext
{
public:
	CfgCtxColumn(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxColumn() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXSCHEMAS_HH_
