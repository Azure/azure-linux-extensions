// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _MDSTIME_HH_
#define _MDSTIME_HH_

#include <iostream>
#include <ctime>
extern "C" {
#include <sys/time.h>
}
#include <boost/date_time/posix_time/posix_time_types.hpp>
#include <micxx/datetime.h>
#include <cpprest/asyncrt_utils.h>

class MdsTime
{
	// <summary>This friend function outputs the ISO8601 formatted string representing the time
	// to the stream</summary>
	friend std::ostream& operator<<(std::ostream& os, const MdsTime& ft);
	friend MdsTime operator+(const MdsTime &left, const MdsTime &right);
	friend MdsTime operator-(const MdsTime &left, const MdsTime &right);
	friend MdsTime operator+(const MdsTime &left, time_t seconds);
public:
	MdsTime() { Touch(); }
	MdsTime(time_t sec, suseconds_t usec = 0) : tv { sec, usec } {}
	MdsTime(const struct timeval &src) { tv.tv_sec = src.tv_sec; tv.tv_usec = src.tv_usec; }
	MdsTime(const MdsTime &src) { tv.tv_sec = src.tv.tv_sec; tv.tv_usec = src.tv.tv_usec; }
	MdsTime(const std::string &rfc3339);
	MdsTime(const mi::Datetime&);
	MdsTime(const utility::datetime&);

	/// <summary>Create an MdsTime initialized to "now". Identical to the default constructor, but it's
	/// explicit about what's going on so that code is easier for people to understand.</summary>
	static MdsTime Now() { return MdsTime(); }
	/// <summary>Create an MdsTime set to the maximum supported time for the implementation (some
	/// time in 2038, for 32-bit time_t values).</summary>
	static MdsTime Max();

	static MdsTime FromIS8601Duration(const std::string &is8601);

	void Touch() { (void)gettimeofday(&tv, 0); }

	// void RoundDown(time_t interval) { if (interval > 0) tv.tv_sec -= tv.tv_sec % interval; }
	MdsTime Round(time_t n) const { time_t sec = tv.tv_sec; if (n > 1) sec -= sec % n; return MdsTime(sec, 0); }

	MdsTime RoundTenDay() const;

	double Elapsed() const { MdsTime res; res -= *this; return (double(res.tv.tv_sec) + (double(res.tv.tv_usec) / 1000000.)); }

	MdsTime& operator=(const MdsTime& src) { tv.tv_sec = src.tv.tv_sec; tv.tv_usec = src.tv.tv_usec; return *this; }
	MdsTime& operator=(const time_t seconds) { tv.tv_sec = seconds; tv.tv_usec = 0; return *this; }

	MdsTime& operator+=(const MdsTime &right);
	MdsTime& operator-=(const MdsTime &right);

	MdsTime& operator+=(const time_t seconds) { tv.tv_sec += seconds; return *this; }

	bool operator==(const MdsTime &t) const { return (tv.tv_sec == t.tv.tv_sec && tv.tv_usec == t.tv.tv_usec); }
	bool operator!=(const MdsTime &t) const { return !(*this == t); }
	bool operator>=(const MdsTime &t) const { return (tv.tv_sec > t.tv.tv_sec || (tv.tv_sec == t.tv.tv_sec && tv.tv_usec >= t.tv.tv_usec)); }
	bool operator<(const MdsTime &t) const { return ! (*this >= t); }
	bool operator>(const MdsTime &t) const { return (tv.tv_sec > t.tv.tv_sec || (tv.tv_sec == t.tv.tv_sec && tv.tv_usec > t.tv.tv_usec)); }
	bool operator<=(const MdsTime &t) const { return ! (*this > t); }

	// Returns true if either tv_sec or tv_usec is true (i.e. non-zero)
	explicit operator bool() const { return (tv.tv_sec || tv.tv_usec); }


	time_t to_time_t() const { return tv.tv_sec; }

	unsigned long long to_FILETIME() const;
	unsigned long long to_DateTime() const;
	boost::posix_time::ptime to_ptime() const;
	boost::posix_time::time_duration to_duration() const;
	utility::datetime to_pplx_datetime() const;

	void GetYMD(std::ostream& fn) const;

	/// <summary>Convert the time to an ISO 8601 string, encoded in UTF-8 (ASCII, technically, but they
	/// amount to the same thing for this particular string).</summary>
	std::string to_iso8601_utf8() const;

	/// <summary>Convert the time to an ISO 8601 string, encoded in UTF-16.</summary>
	std::u16string to_iso8601_utf16() const;

	/// <summary>Convert the time to a custom-formatted date-time string.
	/// Example format string: "y=%Y/m=%m/d=%d/h=%H/m=%M".
	/// The internal buffer size is limited to 256 bytes (including the null-terminating char)
	/// and this function may throw an exception if the resulting string is to be much bigger than that.
	/// Also, the format string should NOT result in a valid empty string (e.g., "%p", which might
	/// be an empty string in some locales), to simplify detection of such a situation of
	/// an exceedingly long result string. Note that the input format string is NOT checked
	/// for such a case. It's the caller's responsibility.</summary>
	std::string to_strftime(const char* format) const;

	// 23:59:59.9999999 UTC, December 31, 9999 in the Gregorian calendar, exactly one 100-nanosecond tick before
	// 00:00:00 UTC, January 1, 10000
	static const unsigned long long MaxDateTimeTicks   = 3155378975999999999ULL;

	// This is a "magic number" date/time for MDS which is used in certain table entries when a fake timestamp
	// is required (e.g. MDS SchemasTable entries)
	static const unsigned long long FakeTimeStampTicks =  504911232000000001ULL;

private:
	struct timeval tv;

	const unsigned long long ticks_per_second = 10000000ULL;
	const unsigned long long epoch_difference = 11644473600ULL;

};

std::ostream& operator<<(std::ostream& os, const MdsTime& ft);
MdsTime operator+(const MdsTime &left, const MdsTime &right);
MdsTime operator-(const MdsTime &left, const MdsTime &right);

#endif // _MDSTIME_HH_

// vim: se sw=8 :
