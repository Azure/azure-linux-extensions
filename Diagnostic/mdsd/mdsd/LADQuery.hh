// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _LADQUERY_HH_
#define _LADQUERY_HH_

#include "Pipeline.hh"
#include "MdsEntityName.hh"
#include <string>
#include <unordered_map>
#include <cfloat>

// Pipe stages must implement the Process method.
// Pipe stages that retain data must implement the Done method.
// Pipe stages must implement a constructor, which can have any parameters that might be required.

namespace Pipe {

class LADQuery : public PipeStage
{
public:
	// Deliberately call-by-value.
	LADQuery(std::string valueAN, std::string nameAN, std::string pkey, std::string uuid);

	void Start(const MdsTime QIbase);
	void Process(CanonicalEntity *);
	const std::string& Name() const { return _name; }
	void Done();

private:
	static const std::string _name;
	const std::string	_valueAttrName;
	const std::string	_nameAttrName;
	const std::string	_pkey;
	const std::string	_uuid;
	MdsTime		_lastSampleTime;
	MdsTime		_startOfSample;

	std::string EncodeAndHash(const std::string &, size_t);

	// Contains aggregated stats on a counter during processing of a LADQuery
	class FullAggregate
	{
	public:
		FullAggregate() : _total(0.0), _minimum(DBL_MAX), _maximum(-DBL_MAX), _last(0.0), _count(0) {}
		void Sample(double value);
		double Total() const { return _total; }
		double Minimum() const { return _minimum; }
		double Maximum() const { return _maximum; }
		double Last() const { return _last; }
		long Count() const { return _count; }
		double Average() const { return _count?(_total / _count):0.0; }

	private:
		double _total;
		double _minimum;
		double _maximum;
		double _last;
		long   _count;
	};

	// Holds all the instances of aggregation stats during processing.
	// Cleared after each run. Bad things will happen if multiple threads
	// call LADQuery::Process, which really shouldn't happen.
	std::unordered_map<std::string, FullAggregate> _savedStats;

};

}


#endif // _LADQUERY_HH_

// vim: se ai sw=8 :
