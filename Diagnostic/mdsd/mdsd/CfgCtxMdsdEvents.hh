// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _CFGCTXMDSDEVENTS_HH_
#define _CFGCTXMDSDEVENTS_HH_

#include "CfgContext.hh"
#include "CfgCtxError.hh"
#include <map>
#include "Subscription.hh"

class LocalSink;

class CfgCtxMdsdEvents : public CfgContext
{
public:
	CfgCtxMdsdEvents(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxMdsdEvents() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { warn_if_attributes(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};


class CfgCtxMdsdEventSource : public CfgContext
{
public:
	CfgCtxMdsdEventSource(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxMdsdEventSource() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t&
		GetSubelementMap() const { return (_source.empty())?(CfgCtxError::subelements):(_subelements); }

	void Enter(const xmlattr_t& properties);

	const std::string& Source() { return _source; }
	LocalSink * Sink() { return _sink; }

private:
	static subelementmap_t _subelements;
	static std::string _name;

	std::string _source;
	LocalSink *_sink;
};

class CfgCtxRouteEvent : public CfgContext
{
public:
	CfgCtxRouteEvent(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxRouteEvent() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties);
	CfgContext* Leave();

private:
	static subelementmap_t _subelements;
	static std::string _name;

	Subscription* _subscription;
	StoreType::Type _storeType;
	CfgCtxMdsdEventSource* _ctxEventSource;
	bool _doSchemaGeneration;
};

class CfgCtxFilter : public CfgContext
{
public:
	CfgCtxFilter(CfgContext* config) : CfgContext(config) {}
	virtual ~CfgCtxFilter() { }

	virtual const std::string& Name() const { return _name; }
	virtual const subelementmap_t& GetSubelementMap() const { return _subelements; }

	void Enter(const xmlattr_t& properties) { log_entry(properties); }

private:
	static subelementmap_t _subelements;
	static std::string _name;
};

#endif //_CFGCTXMDSDEVENTS_HH_
