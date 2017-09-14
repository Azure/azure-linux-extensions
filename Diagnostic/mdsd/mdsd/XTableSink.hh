// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _XTABLESINK_HH_
#define _XTABLESINK_HH_

#include "IMdsSink.hh"
#include <vector>
#include <string>
#include <memory>
#include "stdafx.h"
#include "IdentityColumns.hh"
#include "MdsTime.hh"
#include "MdsEntityName.hh"

class CanonicalEntity;
class Credentials;
class MdsdConfig;
class XTableRequest;

class XTableSink : public IMdsSink
{
public:
	virtual bool IsXTable() const { return true; }

	XTableSink(MdsdConfig* config, const MdsEntityName &target, const Credentials* c);

	virtual ~XTableSink();

	virtual void AddRow(const CanonicalEntity&, const MdsTime&);

	virtual void Flush();
private:
	XTableSink();
	void ComputeConnString();

	MdsdConfig* _config;
	MdsEntityName _target;
	const Credentials* _creds;

	ident_vect_t _identityColumns;
	std::string _identColumnString;

	MdsTime _QIBase;
	std::string _pkey;
	std::string _TIMESTAMP;
	std::string _N;

	std::string _connString;
	std::string _fullTableName;
	MdsTime _rebuildTime;

	std::unique_ptr<XTableRequest> _request;
	unsigned long _estimatedBytes;
};

#endif // _XTABLESINK_HH_

// vim: se sw=8 :
