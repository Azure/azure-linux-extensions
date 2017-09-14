// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _MDSVALUE_HH_
#define _MDSVALUE_HH_

#include <functional>
#include <string>
#include <iostream>
#include <sstream>
#include <cstdint>

#include <micxx/dinstance.h>
#include <micxx/datetime.h>
//#include <micxx/types.h>

extern "C" {
#include "cJSON.h"
}

#include "MdsTime.hh"

class MdsValue {
	friend std::ostream& operator<<(std::ostream& os, const MdsValue& mv);

public:
	enum MdsType { mt_bool, mt_wstr, mt_float64, mt_int32, mt_int64, mt_utc };
	MdsType type;
	union {
		bool bval;
		long lval;
		long long llval;
		double dval;
		utility::datetime datetimeval;
		const std::string * strval;
	};

	~MdsValue() { if ((type == mt_wstr) && strval) { delete strval; } }

	// Type converters. These all return a new MdsValue, copied from the original input,
	// which the caller will be expected to delete.
	MdsValue(bool v) { type = mt_bool; bval = v; }
	MdsValue(long v) { type = mt_int32; lval = v; }
	MdsValue(long long v) { type = mt_int64; llval = v; }
	MdsValue(double v) { type = mt_float64; dval = v; }
	MdsValue(utility::datetime v) { type = mt_utc; datetimeval = v; }
	MdsValue(const std::string& v) { type = mt_wstr; strval = new std::string(v); }
	MdsValue(std::string&& v) { type = mt_wstr; strval = new std::string(std::move(v)); }
	MdsValue(const char * v) { type = mt_wstr; strval = new std::string(v); }
	MdsValue(const std::ostringstream & str) { type = mt_wstr; strval = new std::string(str.str()); }
	MdsValue(const MdsTime&);
	MdsValue(const mi::Datetime&);
	MdsValue(const MI_Value&, mi::Type);

	MdsValue(const MdsValue&);			// Copy constructor
	MdsValue(MdsValue&&) = delete;			// No move-constructor
	MdsValue* operator=(const MdsValue&) = delete;	// No copy-assignment
	MdsValue& operator=(MdsValue&&);		// Move assignment

	static MdsValue* time_t_to_utc(cJSON* src);
	static MdsValue* double_time_t_to_utc(cJSON* src);
	static MdsValue* sec_usec_to_utc(long sec, long fraction) { return new MdsValue(MdsTime(sec, fraction)); }
	static MdsValue* rfc3339_to_utc(cJSON* src);

	// In-place, apply a scale factor to the numeric value. Silently do nothing if the
	// value is non-numeric.
	void scale(double);

	bool IsString() const { return (type == mt_wstr); }
	bool IsNumeric() const { return (type == mt_float64 || type == mt_int32 || type == mt_int64); }

	std::string ToString() const;
	std::string ToJsonSerializedString() const;
	double ToDouble() const;
	std::string TypeToString() const;

private:
	MdsValue();				// No void constructor (no "NULL" objects)
	
	//static std::string omi_time_to_string(const mi::Datetime& x);
	//static std::string sec_usec_to_string(long sec, long fraction);
	template <typename T> static std::string * Array2Str(const mi::Array<T>&);
};

typedef std::function<MdsValue* (cJSON* in)> typeconverter_t;

std::ostream& operator<<(std::ostream& os, const MdsValue& mv);

#endif //_MDSVALUE_HH_

// vim: se sw=8 :
