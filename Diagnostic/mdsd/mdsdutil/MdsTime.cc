// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "MdsTime.hh"
#include <string>
#include <iomanip>
#include <limits>
#include <boost/regex.hpp>
#include <boost/date_time/posix_time/conversion.hpp>
#include "Utility.hh"

MdsTime::MdsTime(const std::string &rfc3339)
{
	struct tm tm;

	std::string decoded = MdsdUtil::UriDecode(rfc3339);
	strptime(decoded.c_str(), "%Y-%m-%dT%TZ", &tm);
	tv.tv_sec = timegm(&tm);
	tv.tv_usec = 0;
}

MdsTime::MdsTime(const mi::Datetime& x)
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

        tv.tv_sec = time1 + 60 * utc;
        tv.tv_usec = us;
}

MdsTime::MdsTime(const utility::datetime& dt) {
	auto interval = dt.to_interval();
	tv.tv_usec = (interval % ticks_per_second) / 10;
	tv.tv_sec = (interval / ticks_per_second) - epoch_difference;
}

MdsTime
MdsTime::Max()
{
	return MdsTime(std::numeric_limits<time_t>::max());
}

MdsTime
MdsTime::FromIS8601Duration(const std::string &is8601)
{
	// Use a regex to extract the various fields. Since we only care about short-ish periods,
	// the regex will only handle days, hours, minutes, and seconds; we skip months and years
	// due to their variability. And we truncate fractions of seconds.
	//
	boost::regex re { "P(([0-9]+)D)?T(([0-9]+)H)?(([0-9]+)M)?(([0-9]+)(.[0-9]+)?S)?" };
	// Submatch 0 is the whole thing
	// Submatch 2 is the number of days
	// Submatch 4 is the number of hours
	// Submatch 6 is the number of minutes
	// Submatch 8 is the number of whole seconds
	boost::smatch matches;
	if (boost::regex_match(is8601, matches, re)) {
		// Got a match. "matches" contains the matching data
		unsigned long seconds = 0;
#define FIELD_TO_SECONDS(FN, SECS) (std::stoul(std::string(matches[FN].first, matches[FN].second))) * SECS
		if (matches[2].matched) {
			seconds += FIELD_TO_SECONDS(2, 24*60*60);
		}
		if (matches[4].matched) {
			seconds += FIELD_TO_SECONDS(4, 60*60);
		}
		if (matches[6].matched) {
			seconds += FIELD_TO_SECONDS(6, 60);
		}
		if (matches[8].matched) {
			seconds += FIELD_TO_SECONDS(8, 1);
		}
		return MdsTime(seconds);
	} else {
		return MdsTime(0);
	}
}

unsigned long long
MdsTime::to_FILETIME() const
{
	return  (epoch_difference + (unsigned long long)tv.tv_sec) * ticks_per_second 
	      + (unsigned long long)tv.tv_usec * 10;
}

boost::posix_time::ptime
MdsTime::to_ptime() const
{
	return boost::posix_time::from_time_t(tv.tv_sec) + boost::posix_time::microseconds(tv.tv_usec);
}

boost::posix_time::time_duration
MdsTime::to_duration() const
{
	return boost::posix_time::seconds(tv.tv_sec) + boost::posix_time::microseconds(tv.tv_usec);
}

MdsTime
MdsTime::RoundTenDay() const
{
	unsigned long long ft = to_FILETIME();

	ft -= ft % (10ULL * 24ULL * 3600ULL * ticks_per_second);

	return MdsTime( (ft / ticks_per_second) - epoch_difference);
}

unsigned long long
MdsTime::to_DateTime() const
{
	return ticks_per_second * ((unsigned long long)tv.tv_sec + 62135596800ULL) + 10ULL * tv.tv_usec;
}

// cpprest/PPLX uses Windows FILETIME as its utility::datetime datatype.
utility::datetime
MdsTime::to_pplx_datetime() const
{
	return utility::datetime() + to_FILETIME();
}


std::ostream&
operator<<(std::ostream& os, const MdsTime& mt)
{
	if (mt.tv.tv_sec == 0 && mt.tv.tv_usec == 0) {
		os << std::string("1601-01-01T00:00:00.0000001Z");
	} else {
		struct tm zulu;
		char timebuf[100];

		(void) gmtime_r(&(mt.tv.tv_sec), &zulu);
		size_t n = strftime(timebuf, sizeof(timebuf), "%Y-%m-%dT%H:%M:%S", &zulu);

		// Note that usec is microseconds, but the Windows DateTime is precise to 100ns. We hard-code
		// an extra 0 to match the required precision.

		os << std::string { timebuf, n };
		os << "." << std::setw(6) << std::setfill('0') << static_cast<unsigned long>(mt.tv.tv_usec) << "0Z";
	}

	return os;
}

std::string
MdsTime::to_iso8601_utf8() const
{
	std::ostringstream buf;
	buf << *this;
	return buf.str();
}

// Rely on the fact that to_iso8601_utf8() produces characters that require only one octet; casting
// each of those to a char16_t is sufficient to convert to UTF-16.
std::u16string
MdsTime::to_iso8601_utf16() const
{
	std::string utf8 = to_iso8601_utf8();
	std::u16string result;
	result.reserve(utf8.length());

	for (const auto & c : utf8) {
		result.push_back(static_cast<std::u16string::value_type>(c));
	}
	return result;
}

std::string
MdsTime::to_strftime(const char* format) const
{
	if (format == nullptr || *format == '\0') {
		return std::string();
	}

	struct tm timeParts;
	time_t time_t_val = to_time_t();
	(void)gmtime_r(&time_t_val, &timeParts);
	char timebuf[256];
	size_t n = strftime(timebuf, sizeof(timebuf), format, &timeParts);
	if (n == 0) { // Too long an output (in rare occasions)
		size_t max_len = strlen(format) * 10;	// Hopefully 10 times is big enough!
		char* buf = static_cast<char*>(malloc(max_len));
		n = strftime(buf, max_len, format, &timeParts);
		if (n == 0) { // Still too big???!!!
			throw std::runtime_error(std::string("MdsTime::to_strftime(): Too big an output string for format \"")
			                         .append(format).append("\""));
		}
		std::string result(buf, n);
		free(buf);
		return result;
	}

	return std::string(timebuf,n);
}

void
MdsTime::GetYMD(std::ostream& strm) const
{
	struct tm brokendown;
	(void)gmtime_r(&(tv.tv_sec), &brokendown);

	strm << brokendown.tm_year+1900;
	strm << std::setfill('0') << std::setw(2) << brokendown.tm_mon+1;
	strm << std::setfill('0') << std::setw(2) << brokendown.tm_mday;
}

MdsTime&
MdsTime::operator+=(const MdsTime &right)
{
	tv.tv_sec += right.tv.tv_sec;
	tv.tv_usec += right.tv.tv_usec;
	time_t sec = tv.tv_usec / 1000000;
	if (sec) {
		tv.tv_sec += sec;
		tv.tv_usec -= 1000000*sec;
	}
	return *this;
}

MdsTime
operator+(const MdsTime &left, const MdsTime &right)
{
	MdsTime answer(left);
	answer += right;
	return answer;
}

MdsTime
operator+(const MdsTime& left, time_t seconds)
{
    MdsTime answer(left);
    answer.tv.tv_sec += seconds;
    return answer;
}

MdsTime&
MdsTime::operator-=(const MdsTime &right)
{
	tv.tv_sec -= right.tv.tv_sec;
	tv.tv_usec -= right.tv.tv_usec;
	while (tv.tv_usec < 0) {
		tv.tv_usec += 1000000;
		tv.tv_sec -= 1;
	}

	return *this;
}

MdsTime
operator-(const MdsTime &left, const MdsTime &right)
{
	MdsTime answer(left);
	answer -= right;
	return answer;
}

// vim: se sw=8 :
