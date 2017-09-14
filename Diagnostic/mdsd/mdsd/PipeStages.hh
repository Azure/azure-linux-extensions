// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _PIPESTAGES_HH_
#define _PIPESTAGES_HH_

#include "Pipeline.hh"
#include "IdentityColumns.hh"
#include "MdsEntityName.hh"
#include "RowIndex.hh"
#include <string>
#include <unordered_set>
#include <unordered_map>

class Batch;

// Used by Pipe::Unpivot to implement <MapName> transforms
struct ColumnTransform
{
public:
	std::string Name;
	double Scale;

	ColumnTransform(std::string name, double scale = 1.0) : Name(name), Scale(scale) {}
};

// Pipe stages must implement the Process method.
// Pipe stages that retain data must implement the Done method.
// Pipe stages must implement a constructor, which can have any parameters that might be required.

namespace Pipe {

class Unpivot : public PipeStage
{
public:
	Unpivot(const std::string &valueName, const std::string &nameName, const std::string &columns,
		std::unordered_map<std::string, ColumnTransform>&& transforms);
	// ~Unpivot() {}

	void Process(CanonicalEntity *);
	const std::string& Name() const { return _name; }

private:
	static const std::string _name;
	const std::string _valueName;
	const std::string _nameName;
	std::unordered_set<std::string> _columns;
	std::unordered_map<std::string, ColumnTransform> _transforms;
};

// BatchWriter class is the final stage in a pipe and is responsible for getting the CanonicalEntity ready for
// consumption by the sink that lies behind the batch. The principal task is managing the PartitionKey and
// RowKey that are needed by some, but not all, sinks.
// If Start() is called, then Done() must be called. If no call Start() is made, there's no need to call Done.
// StoreType::XTable expects Start/Done pairs so it can correctly generate partition keys.
class BatchWriter : public PipeStage
{
public:
	BatchWriter(Batch * b, const ident_vect_t *idvec, unsigned int pcount, StoreType::Type storeType);

	void Process(CanonicalEntity *);
	const std::string& Name() const { return _name; }
	void Start(const MdsTime QIBase) { _qibase = QIBase; }
	void AddSuccessor(PipeStage *) { throw std::logic_error("BatchWriter stage may not have a successor stage"); }
	void Done();

private:
	static const std::string _name;
	Batch *_batch;
	const ident_vect_t * _idvec;
	std::string _identString;
	StoreType::Type _storeType;
	std::string _Nstr;

	MdsTime _qibase;
};

// Add "Identity" columns to the CanonicalEntity and pass it along
class Identity : public PipeStage
{
public:
	Identity(const ident_vect_t * idvec) : _idvec(idvec) {}

	void Process(CanonicalEntity *);
	const std::string& Name() const { return _name; }

private:
	static const std::string _name;
	const ident_vect_t * _idvec;
};

// Build the MDS server-side schema based on the CanonicalEntity. If the combination of schema and full table name
// (with NDay suffix as appropriate) has not yet been pushed to the matching SchemasTable, arrange for that to happen.
class BuildSchema : public PipeStage
{
public:
	BuildSchema(MdsdConfig *config, const MdsEntityName &target, bool schemaIsFixed);

	void Process(CanonicalEntity *);
	const std::string& Name() const { return _name; }

private:
	static const std::string _name;
	const MdsEntityName _target;
	bool		_schemaIsFixed;
	bool		_schemaRequired;
	std::string	_lastFullName;
	std::string	_moniker;
	std::string	_agentIdentity;
	Batch*		_batch;

	static std::unordered_set<std::string> _pushedSchemas;
};


}

#endif // _PIPESTAGES_HH_

// vim: se ai sw=8 :
