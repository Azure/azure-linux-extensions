// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Utility.hh"
#include "MdsTime.hh"
#include <string>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <cstring>
#include <boost/tokenizer.hpp>
#include <boost/regex.hpp>
#include <algorithm>
#include <cctype>
#include <vector>

extern "C" {
#include <sys/uio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/un.h>
}

//////// Begin MdsdUtil namespace

namespace MdsdUtil {

void
ReplaceSubstring(std::string& str, const std::string& from, const std::string& to)
{
	size_t pos = 0;
	while ((pos = str.find(from, pos)) != std::string::npos) {
		str.replace(pos, from.length(), to);
		pos += to.length();
	}
}

// Replace escaped characters with the actual character. Because ampersand is an escapable character,
// it's possible than an escape sequence was, itself, escaped; this function iterates until there are
// no remaining escape sequences.
std::string
UnquoteXmlAttribute(std::string target)
{
	static std::vector<std::pair<std::string, std::string>>
	conversions { { "&lt;", "<" }, { "&gt;", ">" }, { "&apos;", "'" }, { "&#39;", "'" }, { "&quot;", "\"" } };
	bool more_work;

	if (target.length() >= 4) {	// Shortest escape sequence is 4 characters
		do {
			size_t before = target.length();
			// If I replace an &amp; escape, I may have created a new legit escape sequence
			ReplaceSubstring(target, "&amp;", "&");
			ReplaceSubstring(target, "&#38;", "&");
			more_work = (target.length() < before);
		} while (more_work);
		for (const auto & repl : conversions) {
			ReplaceSubstring(target, repl.first, repl.second);
		}
	}
	return target;
}

bool
NotValidName(const std::string& str)
{
	if (str.length() == 0 || str.find(" ") != std::string::npos)
		return true;

	return false;
}

std::string
Join(const std::vector<std::string>& vec, const std::string& sep)
{
	std::string result { "" };

	for (auto it = vec.begin(); it != vec.end(); /*deliberately empty*/ ) {
		result.append(*it);
		++it;
		if (it != vec.end()) {
			result.append(sep);
		}
	}
	return result;
}

unsigned long long
EasyHash(const std::string& str)
{
	unsigned long long strhash = 0;
	const unsigned long long c_Multiplier = 37;
	for(size_t i = 0; i < str.size(); i++) {
		strhash = c_Multiplier * strhash + (unsigned int)str[i];
	}
	return strhash;
}

std::string
ZeroFill(unsigned long long num, size_t len)
{
	std::stringstream s1;
	s1 << std::setfill('0') << std::setw(len) << num;
	return s1.str();
}

// Convert seconds+microseconds to an RFC3339 string with 100ns resolution
std::string
Rfc3339(const time_t sec, const suseconds_t usec)
{
	// Special case: 0.0 is the beginning of the Windows DateTime Epoch
	if (sec == 0 && usec == 0) {
		return std::string("1601-01-01T00:00:00.0000001Z");
	}

	struct tm zulu;
	char timebuf[100];

	(void) gmtime_r(&sec, &zulu);
	size_t n = strftime(timebuf, sizeof(timebuf), "%Y-%m-%dT%H:%M:%S", &zulu);

	// Note that usec is microseconds, but the Windows DateTime is precise to 100ns. We hard-code
	// an extra 0 to match the required precision.

	std::ostringstream result;
	result << std::string { timebuf, n };
	result << "." << std::setw(6) << std::setfill('0') << static_cast<unsigned long>(usec) << "0Z";

	return result.str();
}

// Get the RFC3339 form of the current date/time
std::string
Rfc3339()
{
	struct timeval tv;

	(void)gettimeofday(&tv, 0);

	return MdsdUtil::Rfc3339(tv.tv_sec, tv.tv_usec);
}

// Code below is based on and slightly modified from Glib's g_time_Val_from_iso8601(),
// which is not really fully ISO8601-compliant.
//
// Valid examples for this code:
//    "2015-12-17T08:53:45.123456Z" (Z: UTC)
//    "20151217T085345.123456Z"
//    "2015-12-17T08:53:45.123456" (Local timezone)
//    "2015-12-17T08:53:45" (Fractional second is optional)
//    "2015-12-17T08:53:45,123-08:00" (UTC-08:00, ',' can be used for fractional second)
//    "2015-12-17" (Time portition is optional--treated as 00:00:00)
//    "2015-12-17-08:00" (TZD can be still given with date only)
//
// Non-delimited date/time with reduced size (e.g., YYYY instead of YYYYMMDD) will
// result in incorrect result, and it's not supported by this code.
//   (e.g., "20151217T0853" will be treated as "2015-12-17T00:08:53", not "2015-12-17T08:53:00.000"
//          as stated in ISO8601)
bool
TimeValFromIso8601Restricted(const char* datetime, long& secondsOut, long& uSecondsOut)
{
	if (datetime == nullptr)
	{
		return false;
	}

	while (isspace(*datetime))
	{
		++datetime;
	}

	if (*datetime == '\0' || !isdigit(*datetime))
	{
		return false;
	}

	struct tm _tm;
	memset(&_tm, 0, sizeof(_tm));

	// Date
	long parsedVal = strtoul(datetime, (char**)&datetime, 10);
	bool isDateDelimited = false;
	if (*datetime != '-')
	{
		// YYYYMMDD
		_tm.tm_year = parsedVal / 10000 - 1900;
		_tm.tm_mon = (parsedVal % 10000) / 100 - 1; // January is 0
		_tm.tm_mday = parsedVal % 100;
	}
	else
	{
		// YYYY-MM-DD
		isDateDelimited = true;
		_tm.tm_year = parsedVal - 1900;
		++datetime;
		_tm.tm_mon = strtoul(datetime, (char**)&datetime, 10) - 1;
		if (*datetime != '-')
		{
			return false;
		}
		++datetime;
		_tm.tm_mday = strtoul(datetime, (char**)&datetime, 10);
	}

	if (*datetime == 'T')
	{
		// Time
		++datetime;
		if (!isdigit(*datetime))
		{
			return false;
		}

		parsedVal = strtoul(datetime, (char**)&datetime, 10);
		const bool isTimeDelimited = *datetime == ':';
		if (isTimeDelimited != isDateDelimited)
		{ // Time must be delimited if and only if date is delimited.
			return false;
		}

		if (!isTimeDelimited)
		{
			// hhmmss
			_tm.tm_hour = parsedVal / 10000;
			_tm.tm_min = (parsedVal % 10000) / 100;
			_tm.tm_sec = parsedVal % 100;
		}
		else
		{
			// hh:mm:ss
			_tm.tm_hour = parsedVal;
			++datetime;
			_tm.tm_min = strtoul(datetime, (char**)&datetime, 10);
			if (*datetime != ':')
			{
				return false;
			}
			++datetime;
			_tm.tm_sec = strtoul(datetime, (char**)&datetime, 10);
		}

		// Fractional seconds
		uSecondsOut = 0;
		if (*datetime == '.' || *datetime == ',')
		{
			++datetime;
			long multiplier = 100000;
			parsedVal = 0;
			while (isdigit(*datetime))
			{
				parsedVal += multiplier * (*datetime - '0');
				multiplier /= 10;
				++datetime;
			}
			uSecondsOut = parsedVal;
		}
	}

	// Timezone
	long offsetSec = 0;
	auto makeTimeFunc = timegm; // To switch between UTC or local time. UTC by default.
	if (*datetime == '+' || *datetime == '-')
	{
		int sign = *datetime == '+' ? -1 : 1; // Note the sign inversion
		++datetime;
		parsedVal = strtoul(datetime, (char**)&datetime, 10);

		const bool isTimezoneDelimited = *datetime == ':';
		if (isTimezoneDelimited != isDateDelimited)
		{ // Timezone must be delimited if and only if date is delimited.
			return false;
		}

		if (!isTimezoneDelimited)
		{
			// hhmm
			offsetSec = 3600 * (parsedVal / 100) + 60 * (parsedVal % 100);
		}
		else
		{
			// hh:mm
			offsetSec = 3600 * parsedVal;
			++datetime;
			offsetSec += strtoul(datetime, (char**)&datetime, 10);
		}
		offsetSec *= sign;
	}
	else if (*datetime != 'Z') // No UTC, no offset, so local time
	{
		_tm.tm_isdst = -1;
		makeTimeFunc = mktime;
	}
	else // *datetime == 'Z', nothing else to do except skipping the char
	{
		++datetime;
	}

	// Finally make time (sec since Epoch)
	secondsOut = makeTimeFunc(&_tm) + offsetSec;

	// Make sure no other non-whitespace char follows
	while (isspace(*datetime))
	{
		++datetime;
	}

	return *datetime == '\0';
}

time_t
IntervalStart(const time_t sec, const int interval)
{
	if (interval == 0) {
		return sec;
	} 

	return sec - (sec % interval);
}

void
ParseQueryString(const std::string& qry, std::map<std::string, std::string> & elements)
{
	typedef boost::tokenizer<boost::char_separator<char> > tokenizer;
	boost::char_separator<char> ampsep("&");

	tokenizer tokens(qry, ampsep);
	for (const std::string& tok : tokens) {
		size_t pos = tok.find("=");
		if (pos != std::string::npos && pos > 0) {
			elements[tok.substr(0, pos)] = tok.substr(pos+1);
		}
	}
}

bool
IsEmptyOrWhiteSpace(const std::string& str)
{
	return std::all_of(str.cbegin(), str.cend(), isspace);
}

std::string
UriDecode(const std::string &src)
{
	std::string result;
	for (size_t n = 0; n < src.length(); n++) {
		if (src[n] == '%') {
			int decoded = 0;
			std::istringstream str(src.substr(n+1, 2));
			str >> std::hex >> decoded;
			result += static_cast<char>(decoded);
			n += 2;
		} else {
			result += src[n];
		}
	}

	return result;
}

bool
to_bool(const std::string & val)
{
	if (0 == strcasecmp(val.c_str(), "true") || val == "1") {
		return true;
	}
	return false;
}

std::string
to_lower(const std::string & input)
{
	std::string results;
	results.reserve(input.length());
	std::transform(input.begin(), input.end(), std::insert_iterator<std::string>(results, results.begin()), ::tolower);
	return results;
}

unsigned long long
MurmurHash64(const std::string &input, unsigned long seed = 0)
{
	const unsigned long C1 = 0x239b961b;
	const unsigned long C2 = 0xab0e9789;
	const unsigned long C3 = 0x561ccd1b;
	const unsigned long C4 = 0x0bcaa747;
	const unsigned long C5 = 0x85ebca6b;
	const unsigned long C6 = 0xc2b2ae35;
 
	auto length = input.size();
	const char *data = input.c_str();
 
	unsigned long h1 = seed;
	unsigned long h2 = seed;
 
	size_t index = 0;
	while (index + 7 < length)
	{
		unsigned long k1 = (unsigned long)(data[index + 0] | data[index + 1] << 8 | data[index + 2] << 16 | data[index + 3] << 24);
		unsigned long k2 = (unsigned long)(data[index + 4] | data[index + 5] << 8 | data[index + 6] << 16 | data[index + 7] << 24);

		k1 *= C1;
		k1 = RotateLeft(k1, 15);
		k1 *= C2;
		h1 ^= k1;
		h1 = RotateLeft(h1, 19);
		h1 += h2;
		h1 = (h1 * 5) + C3;

		k2 *= C2;
		k2 = RotateLeft(k2, 17);
		k2 *= C1;
		h2 ^= k2;
		h2 = RotateLeft(h2, 13);
		h2 += h1;
		h2 = (h2 * 5) + C4;

		index += 8;
		}
 
	int tail = length - index;
	if (tail > 0)
	{
		unsigned long k1 =
			(tail >= 4) ? (unsigned long)(data[index + 0] | data[index + 1] << 8 | data[index + 2] << 16 | data[index + 3] << 24) :
			(tail == 3) ? (unsigned long)(data[index + 0] | data[index + 1] << 8 | data[index + 2] << 16) :
			(tail == 2) ? (unsigned long)(data[index + 0] | data[index + 1] << 8) :
				      (unsigned long)data[index + 0];
 
		k1 *= C1;
		k1 = RotateLeft(k1, 15);
		k1 *= C2;
		h1 ^= k1;
 
		if (tail > 4)
		{
			unsigned long k2 =
			  (tail == 7) ? (unsigned long)(data[index + 4] | data[index + 5] << 8 | data[index + 6] << 16) :
			  (tail == 6) ? (unsigned long)(data[index + 4] | data[index + 5] << 8) :
				        (unsigned long)data[index + 4];
 
			k2 *= C2;
			k2 = RotateLeft(k2, 17);
			k2 *= C1;
			h2 ^= k2;
		}
	}
 
	h1 ^= (unsigned long)length;
	h2 ^= (unsigned long)length;
 
	h1 += h2;
	h2 += h1;
 
	h1 ^= h1 >> 16;
	h1 *= C5;
	h1 ^= h1 >> 13;
	h1 *= C6;
	h1 ^= h1 >> 16;
 
	h2 ^= h2 >> 16;
	h2 *= C5;
	h2 ^= h2 >> 13;
	h2 *= C6;
	h2 ^= h2 >> 16;
 
	h1 += h2;
	h2 += h1;
 
	return ((unsigned long long)h2 << 32) | (unsigned long long)h1;
}

std::string
GetErrnoStr(int errnum)
{
	char errorstr[256];
	char* errRC = strerror_r(errnum, errorstr, sizeof(errorstr));
	return std::string(errRC);
}

// Write the buffer, followed by a newline, to the fd. This appears to be a lot of code,
// but it does the job in a single syscall without any string copies or construction, and
// throw a std::runtime_error in the unlikely event of an error or short write.
// Throw a unique exception for EWOULDBLOCK so it's easier to handle.
void
WriteBufferAndNewline(int fd, const char * buf, size_t len)
{
	if (buf == nullptr) {
		throw std::invalid_argument("Invalid argument; cannot be nullptr");
	}

	struct iovec iov[2];
	ssize_t total;
	char newline = '\n';

	// Deliberately cast the const away. The C++ standard permits this as long as the
	// caller doesn't actually try to change write to the const object. The POSIX
	// standard defines iovec::iov_base as a void* so the struct definition can be
	// shared with readv() and writev().
	iov[0].iov_base = static_cast<void*>(const_cast<char*>(buf));
	iov[0].iov_len = len;
	total = len;

	iov[1].iov_base = static_cast<void*>(&newline);
	iov[1].iov_len = 1;
	total += 1;

	ssize_t result = writev(fd, iov, sizeof(iov)/sizeof(struct iovec));
	if (result == -1) {
		auto saved_errno = errno;
		if (EWOULDBLOCK == errno) {
			throw would_block();
		} else {
			throw std::system_error(saved_errno, std::system_category(), "writev() failed.");
		}
	} else if (result != total) {
		std::ostringstream msg;
		msg << "Writev() short write: requested " << total << " but wrote " << result;
		throw std::runtime_error(msg.str());
	}
}

void
WriteBufferAndNewline(int fd, const char * buf)
{
	if (buf == nullptr) {
		throw std::invalid_argument("Invalid argument; cannot be nullptr");
	}

	MdsdUtil::WriteBufferAndNewline(fd, buf, strlen(buf));
}

void
WriteBufferAndNewline(int fd, const std::string& msg)
{
	MdsdUtil::WriteBufferAndNewline(fd, msg.c_str(), msg.length());
}

// Convert a multi-byte string (UTF-8) to a wide-char string. On Linux, a wstring is
// a sequence of 32-bit wchar_t characters. The natural encoding would be UTF-32
// (as provided by mbrtowc), but other encodings are possible. In particular, the
// Windows platform expects wstring to be a sequence of 16-bit wchar_t encoded in
// UTF-16. This function converts UTF-8 strings to the wide string expected by Windows
// using the cpprest utf8_to_utf16 function (which returns a std::u16string) and
// copying characters from that into an std::wstring.
std::wstring
to_utf16(const std::string& input)
{
        auto utf16_result = utility::conversions::utf8_to_utf16(input);

        std::wstring result;
        result.reserve(utf16_result.length());

        for (const auto & c : utf16_result) {
		result.push_back((const wchar_t)c);
	}

        return result;
}

bool
CreateDirIfNotExists(const std::string& filepath, mode_t mode)
{
	if (filepath.empty()) {
		throw std::invalid_argument("Invalid, empty file path is given.");
	}

	struct stat sb;
	if (stat(filepath.c_str(), &sb)) {
		auto errnoCopy = errno;
		if (ENOENT != errnoCopy) {
			throw std::system_error(errnoCopy, std::system_category(),
				"stat() failed on file path '" + filepath + "'");
		}
		else {
			if (mkdir(filepath.c_str(), mode)) {
				throw std::system_error(errno, std::system_category(),
					"Failed to mkdir for file path '" + filepath + "'");
			}
			return true;
		}
	}
	if (!S_ISDIR(sb.st_mode)) {
		throw std::runtime_error("File path '" + filepath + "' already exists and is not a directory.");
	}
	return false;
}


std::string
GetStorageAccountNameFromEndpointURL(const std::string& url)
{
    boost::regex re { R"(^\s*(https?://)?([^.]+)\..*$)" }; // Boost regex requires full string match, so ".*$" at the end is needed.
    // Submatch 0 is the whole string
    // Submatch 2 is the account name
    boost::smatch matches;
    if (!boost::regex_match(url, matches, re))
    {
        throw std::runtime_error("Storage account name not found from storage endpoint URL: " + url);
    }

    return std::string(matches[2].first, matches[2].second);
}

std::string
GetEnvironmentVariable(const std::string & VariableName)
{
        char * envariable = getenv(VariableName.c_str());
        if (!envariable) {
		throw std::runtime_error("Variable '" + VariableName + "' not found in environment");
	}

	return std::string(envariable);
}

std::string
GetEnvironmentVariableOrEmpty(const std::string & VariableName)
{
        char * envariable = getenv(VariableName.c_str());
        if (!envariable) {
		return std::string();
	}

	return std::string(envariable);
}

std::string
GetHostname()
{
	char hostnameBuffer[HOST_NAME_MAX];
	(void) gethostname(hostnameBuffer, sizeof(hostnameBuffer));
	return std::string(hostnameBuffer);
}

std::string
GetTenDaySuffix()
{
	std::ostringstream strm;
	MdsTime::Now().RoundTenDay().GetYMD(strm);
	return strm.str();
}


bool
IsRegFileExists(
    const std::string & filepath
    )
{
    if (filepath.empty()) {
        throw std::invalid_argument("IsRegFileExists(): invalid, empty file path is given.");
    }

    struct stat sb;
    auto rtn = stat(filepath.c_str(), &sb);
    mode_t mode = sb.st_mode;
    return (0 == rtn && S_ISREG(mode));
}

bool
IsDirExists(
    const std::string & filepath
    )
{
    if (filepath.empty()) {
        throw std::invalid_argument("IsDirExists(): invalid, empty file path is given.");
    }

    struct stat sb;
    auto rtn = stat(filepath.c_str(), &sb);
    mode_t mode = sb.st_mode;
    return (0 == rtn && S_ISDIR(mode));
}

void
ValidateDirRWXByUser(
    const std::string & filepath
    )
{
	const std::string funcname(__func__);
    if (filepath.empty()) {
        throw std::invalid_argument(funcname + ": invalid, empty file path is given.");
    }

    struct stat sb;
    if (0 != stat(filepath.c_str(), &sb)) {
        throw std::system_error(errno, std::system_category(),
            funcname + ": failed to stat() path: " + filepath);
    }

    auto mode = sb.st_mode;
    if (!S_ISDIR(mode)) {
        throw std::runtime_error(funcname + ": invalid directory: " + filepath);
    }

    if (0 != access(filepath.c_str(), R_OK | W_OK | X_OK)) {
        throw std::system_error(errno, std::system_category(),
            funcname + ": failed to access() path: " + filepath);
    }
}

bool
RemoveFileIfExists(
    const std::string & filepath
    )
{
    if (!IsRegFileExists(filepath)) {
        return false;
    }
    if (unlink(filepath.c_str())) {
        std::string errmsg = MdsdUtil::GetErrnoStr(errno);
        throw std::runtime_error("RemoveFileIfExists(): failed to remove file: '" +
                                 filepath + "'. Reason: " + errmsg);
    }
    return true;
}

bool
RenameFileIfExists(
    const std::string & oldpath,
    const std::string & newpath
    )
{
    if (!IsRegFileExists(oldpath)) {
        return false;
    }
    if (rename(oldpath.c_str(), newpath.c_str())) {
        std::string errmsg = MdsdUtil::GetErrnoStr(errno);
        throw std::runtime_error("RenameFileIfExists(): failed to rename from '" +
                                 oldpath + "' to '" + newpath + "'. Reason: " + errmsg);
    }
    return true;
}

void
CopyFile(
	const std::string & frompath,
	const std::string & topath
	)
{
	if (frompath.empty()) {
		throw std::invalid_argument("CopyFile(): invalid, empty frompath is given.");
	}
	if (topath.empty()) {
		throw std::invalid_argument("CopyFile(): invalid, empty topath is given.");
	}

	struct TmpDeleter {
		std::string m_filename;
		bool m_Delete = true;
		TmpDeleter(const std::string & filename) : m_filename(filename) {}
		~TmpDeleter() {
			if (m_Delete) {
				RemoveFileIfExists(m_filename);
			}
		}
	};

	int fromfd = open(frompath.c_str(), O_RDONLY);
	if (-1 == fromfd) {
		auto errmsg = GetErrnoStr(errno);
		throw std::runtime_error("CopyFile(): failed to open fromfile '" + frompath + "'. Reason: " + errmsg);
	}
	FdCloser fromFdCloser(fromfd);

	int tofd = open(topath.c_str(), O_CREAT | O_WRONLY, 0644);
	if (-1 == tofd) {
		auto errmsg = GetErrnoStr(errno);
		throw std::runtime_error("CopyFile(): failed to open tofile '" + topath + "'. Reason: " + errmsg);
	}
	FdCloser toFdCloser(tofd);
	TmpDeleter tmpDeleter(topath);

	ssize_t bytesRead = 0;
	char buf[4096];
	while((bytesRead = read(fromfd, buf, sizeof(buf))) > 0) {
		if (write(tofd, buf, bytesRead) == -1) {
			auto errmsg = GetErrnoStr(errno);
			throw std::runtime_error("CopyFile(): failed to write to file '" + topath + "'. Reason: " + errmsg);
		}
	}
	if (-1 == bytesRead) {
		auto errmsg = GetErrnoStr(errno);
		throw std::runtime_error("CopyFile(): failed to read from file '" + frompath + "'. Reason: " + errmsg);
	}

	tmpDeleter.m_Delete = false;
}

time_t
GetLastModificationTime(
	const std::string & filename
	)
{
	struct stat sb;
	auto rtn = stat(filename.c_str(), &sb);
	if (rtn) {
		throw std::system_error(errno, std::system_category(), "stat() failed on file '" + filename + "'.");
	}
	return sb.st_mtime;
}

std::string
GetMostRecentlyModifiedFile(
	const std::vector<std::string> & filelist
	)
{
	if (filelist.empty()) {
		throw std::invalid_argument("filelist cannot be empty.");
	}

	if (1 == filelist.size()) {
		return filelist[0];
	}

	uint64_t max_mtime = 0;
	std::string resultFilePath;
	const uint64_t s2ns = 1000*1000*1000;

	for (const auto f : filelist) {
		struct stat sb;
		auto rtn = stat(f.c_str(), &sb);
		if (rtn) {
			throw std::system_error(errno, std::system_category(), "stat() failed on file '" + f + "'.");
		}

		uint64_t mtime = sb.st_mtim.tv_nsec + ((uint64_t)sb.st_mtime)*s2ns;

		if (max_mtime < mtime) {
			max_mtime = mtime;
			resultFilePath = f;
		}
	}
	return resultFilePath;
}

void
MaskSignal(bool isBlock, int signum)
{
    sigset_t ss;
    if (sigemptyset(&ss)) {
        throw std::system_error(errno, std::system_category(), "sigemptyset() failed");
    }

    if (sigaddset(&ss, signum)) {
        throw std::system_error(errno, std::system_category(), "sigaddset() failed");
    }

    int how = isBlock? SIG_BLOCK : SIG_UNBLOCK;
    if (sigprocmask(how, &ss, NULL)) {
        throw std::system_error(errno, std::system_category(), "sigprocmask() failed");
    }
}

void
TouchFileUs(const std::string & filename)
{
    if (utimes(filename.c_str(), NULL)) {
        throw std::system_error(errno, std::system_category(), "utimes(" + filename + ") failed");
    }
}

std::string
GetFileBasename(
    const std::string & filepath
    )
{
    auto p = filepath.find_last_of('/');
    if (p == std::string::npos) {
        return filepath;
    }
    return filepath.substr(p+1);
}


LockedFile::LockedFile(const std::string& filepath) : m_fd(-1)
{
    if (!filepath.empty()) { // Make LockedFile("") the same as LockedFile()
        Open(filepath);
    }
}


void
LockedFile::Open(const std::string& filepath)
{
    if (IsOpen()) {
        if (filepath == m_filepath) { // same file is being opened/locked again, so just noop
            return;
        }
        throw std::logic_error("LockedFile::Open(): The object is already holding a lock on a different file '" + m_filepath + "'");
    }

    m_fd = open(filepath.c_str(), O_WRONLY | O_CREAT, 0644);
    if (-1 == m_fd) {
        auto errmsg = GetErrnoStr(errno);
        throw std::runtime_error("LockedFile::Open(): failed to open file '" + filepath + "'. Reason: " + errmsg);
    }
    if (flock(m_fd, LOCK_EX | LOCK_NB)) {
        if (errno == EWOULDBLOCK) {
            throw AlreadyLocked("LockedFile::Open() : File '" + filepath + "' is already locked");
        }
        auto errmsg = GetErrnoStr(errno);
        throw std::runtime_error("LockedFile::Open(): failed to lock file '" + filepath + "'. Reason: " + errmsg);
    }
    m_filepath = filepath;
}


LockedFile::~LockedFile()
{
    Remove();
}


void
LockedFile::WriteLine(const std::string& line) const
{
    if (!IsOpen()) {
        throw std::runtime_error("LockedFile::WriteLine(): No file has been opened");
    }
    WriteBufferAndNewline(m_fd, line);
}

void
LockedFile::Remove()
{
    if (IsOpen()) {
		// Truncate first
		try {
			RemoveFileIfExists(m_filepath);
		} catch(std::runtime_error& ex) {
			// Remove failed, try to truncate instead.
			if (-1 == ftruncate(m_fd, 0)) {
				auto errmsg = GetErrnoStr(errno);
				throw std::runtime_error("LockedFile::Remove(): Remove failed and failed to truncate file '" + m_filepath + "'. Reason: " + errmsg);
			}
		}
		close(m_fd);
        m_filepath.clear();
        m_fd = -1;
    }
}

void
LockedFile::TruncateAndClose()
{
    if (IsOpen()) {
        if (-1 == ftruncate(m_fd, 0)) {
            auto errmsg = GetErrnoStr(errno);
            throw std::runtime_error("LockedFile::TruncateAndClose(): failed to truncate file '" + m_filepath + "'. Reason: " + errmsg);
        }
        close(m_fd);
        m_filepath.clear();
        m_fd = -1;
    }
}

std::string
StringNCopy(const char* src, size_t maxbytes)
{
    if (!src || maxbytes == 0) {
        return std::string();
    }

    auto len = std::min(maxbytes, strlen(src));
    std::vector<char> dest(len+1);
    memcpy(dest.data(), src, len);
    dest[len] = '\0';
    return std::string(dest.data());
}

std::string GetTid()
{
    pthread_t tid = pthread_self();
    return "Tid-" + std::to_string(tid);

}

FdCloser::~FdCloser()
{
    if (m_fd > -1) {
        close(m_fd);
    }
}

void FdCloser::Release()
{
    m_fd = -1;
}

int32_t
GetNumFileResourceSoftLimit()
{
    struct rlimit rlim;
    if (getrlimit(RLIMIT_NOFILE, &rlim) < 0) {
        throw std::system_error(errno, std::system_category(), "getrlimit() failed");
    }

    if(RLIM_INFINITY == rlim.rlim_cur) {
        return 0;
    }
    return static_cast<int32_t> (rlim.rlim_cur);
}


static std::vector<const char*>&
GetSyslogSeverityStringVector()
{
	static auto v = new std::vector<const char*> (
	{
		"\"Emergency\"", "\"Alert\"", "\"Critical\"", "\"Error\"",
		"\"Warning\"", "\"Notice\"", "\"Informational\"", "\"Debug\""
	});
	return *v;
}


const char*
GetSyslogSeverityStringFromValue(int severity)
{
	auto v = GetSyslogSeverityStringVector();
	if (severity < 0 || severity >= (int) v.size()) {
		return "\"Other\"";
	}
	return v[(size_t) severity];
}

int
CreateAndBindUnixSocket(
    const std::string & sockFilePath
    )
{
    if (sockFilePath.empty()) {
        throw std::invalid_argument("CreateAndBindUnixSocket: socket filepath cannot be empty.");
    }

    struct sockaddr_un addr;

    // maxLength: maximum permitted length of a path of a Unix domain socket
    constexpr auto maxLength = sizeof(addr.sun_path);
    if (sockFilePath.size() > maxLength) {
        throw std::invalid_argument("UnixSockAddr: socketfile '" + sockFilePath +
            "' exceeds max allowed length " + std::to_string(maxLength));
    }

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (-1 == fd)
    {
        throw std::system_error(errno, std::system_category(), "socket(AF_UNIX, SOCK_STREAM)");
    }

    memset(&addr, 0, sizeof(struct sockaddr_un));
    addr.sun_family = AF_UNIX;
    sockFilePath.copy(addr.sun_path, sizeof(addr.sun_path));

    unlink(sockFilePath.c_str());

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)))
    {
        close(fd);
        throw std::system_error(errno, std::system_category(), "bind(AF_UNIX, " + sockFilePath + ")");
    }
    return fd;
}


// Return env var value if set, or default value if not.
// Throw a runtime_error is the specified dir doesn't exist.
std::string
GetEnvDirVar(const std::string& name, const std::string& default_value) {
	char* envConfigDir = std::getenv(name.c_str());
	if (envConfigDir != nullptr) {
		if (!IsDirExists(envConfigDir)) {
			throw std::runtime_error("The directory specified in the environment variable " + name + " does not exist: " + envConfigDir);
		} else {
			return envConfigDir;
		}
	}
	return default_value;
}

void
ParseHttpsOrHttpUrl(const std::string & absUrl, std::string& baseUrl, std::string& params)
{
    std::vector<std::string> supportedPrefixList = { "https://", "http://" };
    for (const auto & prefix : supportedPrefixList) {
        if (absUrl.size() > prefix.size()) {
            if (0 == absUrl.compare(0, prefix.size(), prefix)) {
                auto sepPos = absUrl.find_first_of('/', prefix.size());
                if (sepPos != std::string::npos) {
                    baseUrl = absUrl.substr(0, sepPos);
                    params = absUrl.substr(sepPos);
                }
                else {
                    baseUrl = absUrl;
                    params = "";
                }
                return;
            }
        }
    }

    throw std::invalid_argument("ParseHttpsOrHttpUrl(): Invalid absURL: " + absUrl);
}


};

//////////// MdsdUtil namespace ends


// vim: se sw=8 :
