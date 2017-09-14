// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _IMDSSINK_HH_
#define _IMDSSINK_HH_

#include <string>
#include "StoreType.hh"
#include "MdsTime.hh"
#include "MdsEntityName.hh"

class CanonicalEntity;
class Credentials;
class MdsdConfig;

class IMdsSink
{
public:
	virtual bool IsXTable() const { return false; }
	virtual bool IsBond() const { return false; }
	virtual bool IsXJsonBlob() const { return false; }
	virtual bool IsLocal() const { return false; }
	virtual bool IsFile() const { return false; }

	static IMdsSink* CreateSink(MdsdConfig *, const MdsEntityName &target, const Credentials*);

	virtual void AddRow(const CanonicalEntity&, const MdsTime&) = 0;	// This is a pure virtual class
	virtual void Flush() = 0;
	virtual void ValidateAccess() {}		// Throws if credentials cannot be used to access the target
							// May have desireable initialization side-effect(s)

	IMdsSink() = delete;				// No default constructor
	IMdsSink(const IMdsSink&) = delete;		// No copy constructor

	IMdsSink& operator=(const IMdsSink&) = delete;	// No copy assignment

	IMdsSink(IMdsSink&&) = delete;				// No Move constructor
	virtual IMdsSink& operator=(IMdsSink&&) = delete;	// No Move assignment

	virtual ~IMdsSink() {}
	void SetRetentionPeriod(const MdsTime & period) { if (period > _retentionPeriod) _retentionPeriod = period; }
	const MdsTime RetentionPeriod() const { return _retentionPeriod; }
	time_t RetentionSeconds() const { return _retentionPeriod.to_time_t(); }

	StoreType::Type Type() const { return _type; }

protected:
	IMdsSink(StoreType::Type t) : _type(t), _retentionPeriod(0) {}

private:
	StoreType::Type _type;
	MdsTime _retentionPeriod;
};

#endif // _IMDSSINK_HH_

// vim: se sw=8 :
