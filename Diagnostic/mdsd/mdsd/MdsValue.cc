// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsValue.hh"
#include <cstdlib>
#include <ctime>
#include <cmath>
#include <cstring>
#include <string>
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <boost/lexical_cast.hpp>
#include "Utility.hh"
#include "cpprest/json.h"

// Copy constructor
MdsValue::MdsValue(const MdsValue& src) : type(src.type)
{
	switch(type) {
	case mt_bool:
		bval = src.bval;
		break;
	case mt_int32:
		lval = src.lval;
		break;
	case mt_int64:
		llval = src.llval;
		break;
	case mt_float64:
		dval = src.dval;
		break;
	case mt_wstr:
		strval = new std::string(*(src.strval));
		break;
	case mt_utc:
		datetimeval = src.datetimeval;
		break;
	default:
		throw std::logic_error("Attempt to copy MdsValue of unknown type");
	}
}

// Constructor for MdsTime
MdsValue::MdsValue(const MdsTime& val)
{
	type = mt_utc;
	datetimeval = val.to_pplx_datetime();
}

// Constructor for mi::Datetime
MdsValue::MdsValue(const mi::Datetime& x)
{
	*this = MdsValue(MdsTime(x));
}

// Move assignment operator
MdsValue&
MdsValue::operator=(MdsValue&& src)
{
	type = src.type;

	switch(type) {
	case mt_bool:
		bval = src.bval;
		break;
	case mt_int32:
		lval = src.lval;
		break;
	case mt_int64:
		llval = src.llval;
		break;
	case mt_float64:
		dval = src.dval;
		break;
	case mt_wstr:
		strval = src.strval;
		src.strval = nullptr;
		break;
	case mt_utc:
		datetimeval = src.datetimeval;
		break;
	default:
		throw std::logic_error("Attempt to move-assign MdsValue of unknown type");
	}

	return *this;
}



MdsValue*
MdsValue::time_t_to_utc(cJSON* src)
{
	if (src->type != cJSON_Number) return 0;
	if (src->valueint > LONG_MAX) return 0;

	return new MdsValue(MdsTime(src->valueint, 0));
}

MdsValue*
MdsValue::double_time_t_to_utc(cJSON* src)
{
	if (src->type != cJSON_Number) return 0;
	if (src->valuedouble > double(LONG_MAX) || src->valuedouble < 0.) return 0;

	long sec = int(floor(src->valuedouble));
	long fraction = int(floor(1000000. * (src->valuedouble - floor(src->valuedouble))));

	return MdsValue::sec_usec_to_utc(sec, fraction);
}

MdsValue*
MdsValue::rfc3339_to_utc(cJSON* src)
{
	if (src->type != cJSON_String) return 0;

	size_t n = strlen(src->valuestring);
	if (n < 19) return 0;	// Minimum legal length of an RFC 3339 datetime string

	long tv_sec = 0, tv_usec = 0;
	if (!MdsdUtil::TimeValFromIso8601Restricted(src->valuestring, tv_sec, tv_usec)) return 0;

	return MdsValue::sec_usec_to_utc(tv_sec, tv_usec);
}

void
MdsValue::scale(double factor)
{
	switch(type) {
	case mt_bool:
	case mt_wstr:
	case mt_utc:
	default:
		break;
	case mt_int32:
		dval = factor * ((double)lval);
		type = mt_float64;
		break;
	case mt_int64:
		dval = factor * ((double)llval);
		type = mt_float64;
		break;
	case mt_float64:
		dval = factor * dval;
		break;
	}
}


// The OMI conversions are mostly mechanical, but templatizing them is pretty ugly due to the discriminated
// unions in the MI_Value and MdsValue objects. It's // easy enough to use a macro to generate the common case:
//
// case MI_BOOLEAN:
//	type = mt_bool;
//	bval = (bool) value.boolean;
//	break;
// case MITYPE:
//	type = MTTYPE;
//	MEMBER = (CTYPE)(value.UNIONARM);
#define CVTUNARY(MITYPE, MTTYPE, MEMBER, CTYPE, UNIONARM) case MITYPE: type = MTTYPE; MEMBER = (CTYPE)(value.UNIONARM); break;

// Arrays are a bit easier via macro; the MTTYPE, MEMBER, and CTYPE always correspond to strings.
template <typename ARRTYPE> static std::string *
OMIarray2string(ARRTYPE arm)
{
	std::ostringstream result;
	for (MI_Uint32 idx = 0; idx < arm.size; idx++) {
		auto val = arm.data[idx];
		if (idx) {
			result << ", ";
		}
		result << val;
	}
	return new std::string(result.str());
}
#define CVTARRAY(MITYPE, TYPE, UNIONARM) case MITYPE: type=mt_wstr; strval=OMIarray2string<TYPE>(value.UNIONARM); break;

// And there are some exceptions to the pattern that need to be handled explicitly.

MdsValue::MdsValue(const MI_Value& value, MI_Type fieldtype)
{
	switch(fieldtype)
	{
		CVTUNARY(MI_BOOLEAN, mt_bool, bval, bool, boolean)
		CVTUNARY(MI_SINT8, mt_int32, lval, long, sint8)
		CVTUNARY(MI_UINT8, mt_int32, lval, long, uint8)
		CVTUNARY(MI_SINT16, mt_int32, lval, long, sint16)
		CVTUNARY(MI_UINT16, mt_int32, lval, long, uint16)
		CVTUNARY(MI_SINT32, mt_int32, lval, long, sint32)
		CVTUNARY(MI_UINT32, mt_int64, llval, long long, uint32)
		CVTUNARY(MI_SINT64, mt_int64, llval, long long, sint64)
		CVTUNARY(MI_UINT64, mt_int64, llval, long long, uint64)
		CVTUNARY(MI_REAL32, mt_float64, dval, double, real32)
		CVTUNARY(MI_REAL64, mt_float64, dval, double, real64)
		CVTUNARY(MI_CHAR16, mt_int32, lval, long, char16)

		CVTARRAY(MI_BOOLEANA, MI_BooleanA, booleana)
		CVTARRAY(MI_SINT8A, MI_Sint8A, sint8a)
		CVTARRAY(MI_UINT8A, MI_Uint8A, uint8a)
		CVTARRAY(MI_SINT16A, MI_Sint16A, sint16a)
		CVTARRAY(MI_UINT16A, MI_Uint16A, uint16a)
		CVTARRAY(MI_SINT32A, MI_Sint32A, sint32a)
		CVTARRAY(MI_UINT32A, MI_Uint32A, uint32a)
		CVTARRAY(MI_SINT64A, MI_Sint64A, sint64a)
		CVTARRAY(MI_UINT64A, MI_Uint64A, uint64a)
		CVTARRAY(MI_REAL32A, MI_Real32A, real32a)
		CVTARRAY(MI_REAL64A, MI_Real64A, real64a)
		CVTARRAY(MI_CHAR16A, MI_Char16A, char16a)

        case MI_DATETIME:
		*this = MdsValue(MdsTime(value.datetime));
		break;

        case MI_STRING:
		type = mt_wstr;
		strval = new std::string(value.string);
		break;

        case MI_DATETIMEA:
        {
		type = mt_wstr;
		std::ostringstream result;
		for (MI_Uint32 idx = 0; idx < value.datetimea.size; idx++) {
			if (idx) {
				result << ", ";
			}
			result << MdsTime(value.datetimea.data[idx]);
		}
		strval = new std::string(result.str());
		break;
	}

        case MI_STRINGA:
        {
		type = mt_wstr;
		std::ostringstream result;
		for (MI_Uint32 idx = 0; idx < value.stringa.size; idx++) {
			if (idx) {
				result << ", ";
			}
			result << std::string(value.stringa.data[idx]);
		}
		strval = new std::string(result.str());
		break;
	}

        case MI_INSTANCE:
        case MI_REFERENCE:
        case MI_INSTANCEA:
        case MI_REFERENCEA:
		throw std::runtime_error("MdsValue asked to convert instance/reference");

        default:
		throw std::runtime_error("MdsValue asked to convert unknown MI_Type");
    }
}

#if 0
std::string
MdsValue::omi_time_to_string(const mi::Datetime& x)
{
	MI_Uint32 y,mon,d,h,min,s,us;
	MI_Sint32 utc;
	x.Get(y,mon,d,h,min,s,us,utc);

	struct tm t;
	t.tm_year = y-1900;
	t.tm_mon = mon-1;
	t.tm_mday = d;
	t.tm_hour = h;
	t.tm_min = min;
	t.tm_sec = s;
	t.tm_isdst = -1;  // let mktime() to decide daylight saving adjustment

	time_t time1 = mktime(&t);
	long sec = (long)(time1 + 60 * utc);
	long usec = (long)us;
	return sec_usec_to_string(sec, usec);
}
#endif

std::string
MdsValue::ToString() const
{
	std::ostringstream s;

	s << *this;

	return s.str();
}

double
MdsValue::ToDouble() const
{
	switch(type) {
	case mt_int32:
		return (double) lval;
	case mt_int64:
		return (double) llval;
	case mt_float64:
		return dval;
	case mt_wstr:
		try {
			return boost::lexical_cast<double>(*strval);
		}
		catch(const boost::bad_lexical_cast &) {
			throw std::domain_error("Value is a string which is not a valid floating-point number");
		}
	case mt_utc:
	case mt_bool:
	default:
		throw std::domain_error("Value is not a type which can be converted to float");
	}
}

std::ostream&
operator<<(std::ostream& os, const MdsValue& mv)
{
	switch(mv.type)
	{
		case MdsValue::MdsType::mt_bool:
			if (mv.bval) {
				os << "true";
			}
			else {
				os << "false";
			}
			break;
		case MdsValue::MdsType::mt_int32:
			os << "(int32)" << mv.lval;
			break;
		case MdsValue::MdsType::mt_int64:
			os << "(int64)" << mv.llval;
			break;
		case MdsValue::MdsType::mt_float64:
			os << "(float64)" << mv.dval;
			break;
		case MdsValue::MdsType::mt_wstr:
			os << "(wstr)\"" << *(mv.strval) << "\"";
			break;
		case MdsValue::MdsType::mt_utc:
			os << "(utc)[" << mv.datetimeval.to_string(utility::datetime::ISO_8601) << "]";
			break;
		default:
			os << "(no type)";
			break;
	}

	return os;
}

std::string
MdsValue::ToJsonSerializedString() const
{
	web::json::value jsonValue;

	switch(type)
	{
		case MdsValue::MdsType::mt_bool:
			jsonValue = web::json::value(bval);
			break;
		case MdsValue::MdsType::mt_int32:
			jsonValue = web::json::value(lval);
			break;
		case MdsValue::MdsType::mt_int64:
			jsonValue = web::json::value((int64_t)llval);
			break;
		case MdsValue::MdsType::mt_float64:
			jsonValue = web::json::value(dval);
			break;
		case MdsValue::MdsType::mt_wstr:
			jsonValue = web::json::value(*strval);
			break;
		case MdsValue::MdsType::mt_utc:
			jsonValue = web::json::value(datetimeval.to_string(utility::datetime::ISO_8601));
			break;
		default:
			throw std::logic_error("Attempt to get JSON value string of unknown type");
	}

	return jsonValue.serialize();
}

std::string
MdsValue::TypeToString() const
{
	switch(type) {
	case mt_bool:
		return "mt:bool";
	case mt_int32:
		return "mt:int32";
	case mt_int64:
		return "mt:int64";
	case mt_float64:
		return "mt:float64";
	case mt_wstr:
		return "mt:wstr";
	case mt_utc:
		return "mt:utc";
	}
	throw std::logic_error("Attempt to convert unknown MDS type to string");
}

template <typename T> std::string *
MdsValue::Array2Str(const mi::Array<T>& arr)
{
    auto str = new std::string;
    for (MI_Uint32 i = 0; i < arr.GetSize(); i++) {
        T x = arr[i];
	if (i) {
		str->append(", ");
	}
        str->append(std::to_string(x));
    }
    return str;
}

// vim: se sw=8 :
