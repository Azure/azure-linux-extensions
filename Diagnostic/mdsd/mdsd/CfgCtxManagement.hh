// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXMANAGEMENT_HH_
#define _CFGCTXMANAGEMENT_HH_

#include "CfgContext.hh"
#include <list>

class TableSchema;

class CfgCtxManagement : public CfgContext
{
public:
	CfgCtxManagement(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxManagement() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
	static std::map<std::string, unsigned int> _eventVolumes;
};

class CfgCtxIdentity : public CfgContext
{
public:
	CfgCtxIdentity(CfgContext* config) : CfgContext(config), IdentityWasSet(false) {}
	virtual ~CfgCtxIdentity() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

	void AddString(const std::string& n, const std::string& str);
	void AddEnvariable(const std::string& n, const std::string& varname);

private:
	bool IdentityWasSet;

	static subelementmap_t _subelements;
	static std::string _name;
};

class CfgCtxIdentityComponent : public CfgContext
{
public:
	CfgCtxIdentityComponent(CfgContext* config) : CfgContext(config), _ctxidentity(nullptr) {}
	virtual ~CfgCtxIdentityComponent() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);
	virtual void HandleBody(const std::string& body);
	CfgContext* Leave();

private:
	std::string ComponentName;
	bool IsValid;
	//bool GotBody;
	bool ExtraBody;
	bool IgnoreBody;
	CfgCtxIdentity* _ctxidentity;

	static subelementmap_t _subelements;
	static std::string _name;
};

class CfgCtxAgentResourceUsage : public CfgContext
{
public:
	CfgCtxAgentResourceUsage(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxAgentResourceUsage() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

class CfgCtxOboDirectPartitionField : public CfgContext
{
public:
	CfgCtxOboDirectPartitionField(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxOboDirectPartitionField() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXMANAGEMENT_HH_

// :vim set ai sw=8 :
