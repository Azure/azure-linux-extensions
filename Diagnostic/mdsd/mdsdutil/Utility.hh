// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _UTILITY_HH_
#define _UTILITY_HH_

#include <string>
#include <vector>
#include <ctime>
#include <iostream>
#include <map>

extern "C" {
#include <sys/time.h>
}

namespace MdsdUtil {

/// <summary>Replace all instances of "from" with "to". Proceeds left to right, does not backtrack or rescan</summary>
extern void ReplaceSubstring(std::string& str, const std::string& from, const std::string& to);

/// <summary>Replace standard XML/HTML escapes with the correct character; iterates until all have been converted</summary>
/// <return>The string, without any escape sequences</return>
std::string UnquoteXmlAttribute(std::string target);

/// <summary>Checks if a "name" is valid (not empty, does not contain blanks)</summary>
/// <return>True if argument is not a valid name</return>
extern bool NotValidName(const std::string& str);

/// <summary>Concatenate all the strings in the vector, placing a copy of the separator between each vector element</summary>
extern std::string Join(const std::vector<std::string>&, const std::string&);

/// <summary>Compute easy MDS hash of a string</summary>
extern unsigned long long EasyHash(const std::string& str);

/// <summary>Convert num to a string, zero-pad on the left to a total length of len bytes</summary>
std::string ZeroFill(unsigned long long num, size_t len);

/// <summary>Convert sec+usec to RFC3339 time, with 100ns resolution, in Zulu (GMT)</summary>
std::string Rfc3339(const time_t, const suseconds_t);

/// <summary>Convert current time to RFC3339 time, with 100ns resolution, in Zulu (GMT)</summary>
std::string Rfc3339();

/// <summary>Convert "restricted" ISO8601 time string to sec+usec (replacing g_time_val_from_iso8601())</summary>
/// <return>True if and only if the parsing is successful, and sec/usec will hold the computed values</return>
bool TimeValFromIso8601Restricted(const char* datetimeStr, long& secondsOut, long& uSecondsOut);

/// <summary>Round a time_t down to the nearest multiple of interval seconds</summary>
time_t IntervalStart(const time_t, const int);

/// <summary>Split a query string into a [key,value] map</summary>
void ParseQueryString(const std::string& qry, std::map<std::string, std::string> & elements);

/// <summary> To check whether a given string is empty or all white spaces </summary>
bool IsEmptyOrWhiteSpace(const std::string& str);

/// <summary> To check whether a given string is empty or all white spaces </summary>
//bool IsEmptyOrWhiteSpace(const std::string & str);

/// <summary>Decode a URL</summary>
std::string UriDecode(const std::string &src);

/// <summary>Convert a string to a boolean value</summary>
bool to_bool(const std::string &val);

/// <summmary>Convert an ASCII string to lower case</summary>
/// <returns>A copy of the input string with ASCII upper case characters converted to lower case</returns>
std::string to_lower(const std::string & asciiString);

/// <summary>Rotate an integral type right</summary>
template <class T> T RotateRight(T n, unsigned int count) { count = count%(sizeof(T)*8); if (count == 0) return n; unsigned int complementCount = sizeof(T)*8 - count; return ((n >> count) & ((1LL<<complementCount) - 1LL)) | (n << complementCount); }

/// <summary>Rotate an integral type left</summary>
template <class T> T RotateLeft(T n, unsigned int count) { count = count%(sizeof(T)*8); if (count == 0) return n; return RotateRight(n, sizeof(T)*8 - count); }

/// <summary>Compute 64-bit Murmur hash of a string, with initializer</summary>
unsigned long long MurmurHash64(const std::string&, unsigned long);

/// <summary>Convert a POSIX errno to a string</summary>
std::string GetErrnoStr(int errnum);

inline std::string ToString(bool b)
{
    return b? "true" : "false";
}

class would_block : public std::exception
{
public:
        virtual const char* what() const noexcept { return "EWOULDBLOCK"; }
};

/// <summary>Write a buffer, followed by a newline, to a POSIX file descriptor. Throw appropriate exceptions
/// for short writes or any error reported by writev.</summary>
void WriteBufferAndNewline(int fd, const char * buf, size_t len);
void WriteBufferAndNewline(int fd, const char * buf);
void WriteBufferAndNewline(int fd, const std::string& buf);

/// <summary>Convert a UTF-8 std::string to a std::wstring, encoded in UTF-16, relying on
/// the cpprest library to convert to utf16 in a u16string and copying characters.</summary>
std::wstring to_utf16(const std::string& s);

/// <summary>
/// Create a directory given its path if it doesn't exist.
/// Throw exception if any error.
/// Return true if the directory doesn't exist and is created properly.
/// Return false if the directory is valid and already exists.
/// NOTE: the mode is used only when directory is created in this function.
/// </summary>
bool CreateDirIfNotExists(const std::string& filepath, mode_t mode);

/// <summary>
/// Extracts and returns the storage account name from the passed storage endpoint URL.
/// For example, returns "stgacct", given "https://stgacct.blob.core.windows.net/".
/// If no match is found, an empty string is returned.
/// </summary>
std::string GetStorageAccountNameFromEndpointURL(const std::string& url);

/// <summary>
/// Get the value of a variable from the process environment. Throw std::runtime_error
/// if the variable is not defined in the environment. This is different from the variable
/// being defined as an empty string; that latter case does not throw an error.
/// </summary>
std::string GetEnvironmentVariable(const std::string &);

/// <summary>
/// Get the value of a variable from the process environment. Does not throw an exception
/// if the variable is not defined in the environment; in that case it returns an empty string.
/// </summary>
std::string GetEnvironmentVariableOrEmpty(const std::string &);

/// <summary>Returns the hostname of the running system</summary>
std::string GetHostname();

/// <summary>Get autokey table's 10-day suffix </summary>
std::string GetTenDaySuffix();

/// <summary>
/// Return true if filepath exists and it is a regular file.
/// If filepath is an empty string, throw exception.
/// </summary>
bool IsRegFileExists(const std::string & filepath);

/// <summary>
/// Return true if filepath exists and it is a directory.
/// If filepath is an empty string, throw exception.
/// </summary>
bool IsDirExists(const std::string & filepath);

/// <summary>
/// Make sure that the filepath exists, is a dir, and the running process has
/// read/write/execute access to the dir.
/// Throw exception otherwise.
/// </summary>
void ValidateDirRWXByUser(const std::string & filepath);

/// <summary>
/// If 'filepath' exists, unlink it.
/// Return true if no error and the file is unlinked.
/// Return false if the file doesn't exist.
/// Throw exception for any error.
/// </summary>
bool RemoveFileIfExists(const std::string & filepath);

/// <summary>
/// Rename file from 'oldpath' to 'newpath' if 'oldpath' exists.
/// Return true if no error and the file is successfully renamed.
/// Return false if the file doesn't exist.
/// Throw exception if any error.
/// </summary>
bool RenameFileIfExists(const std::string & oldpath, const std::string & newpath);

/// <summary>
/// Copy file 'frompath' to 'topath'. If 'topath' exists, it will be overwritten.
/// It will throw exception for any error.
/// </summary>
void CopyFile(const std::string & frompath, const std::string & topath);

time_t GetLastModificationTime(const std::string & filename);
/// <summary>
/// Get the last modified file in a given file list.
/// If the list is empty, throw exception.
/// If there are more than one files that meet this criteria, return the first
/// one in the list.
/// </summary>
std::string GetMostRecentlyModifiedFile(const std::vector<std::string> & filelist);

/// <summary>
/// change a file's last modification time to 'now' at micro-second precision.
/// </summary>
void TouchFileUs(const std::string & filename);

/// <summary>Block or unblock a given signal.</summary>
void MaskSignal(bool isBlock, int signum);

/// <summary> Get the basename of a filepath </summary>
std::string GetFileBasename(const std::string & filepath);

/// <summary>Utility class to open a file with exclusive lock, allow
/// writing to it line-by-line, and let the destructor delete the file</summary>
class LockedFile
{
    std::string m_filepath;
    int         m_fd;

public:
    LockedFile() : m_fd(-1) {}

    LockedFile(const std::string& filepath);

    ~LockedFile();

    LockedFile(const LockedFile&) = delete;
    LockedFile(LockedFile&&) = default;
    LockedFile& operator=(const LockedFile&) = delete;
    LockedFile& operator=(LockedFile&&) = default;

    void Open(const std::string& filepath);

    bool IsOpen() const { return !m_filepath.empty(); }

    void WriteLine(const std::string& line) const;

    void Remove();

    void TruncateAndClose();

    class AlreadyLocked : public std::runtime_error
    {
    public:
        AlreadyLocked(const std::string& msg) : std::runtime_error(msg) {}
    };
};

/// Copy maximum of 'maxbytes' from 'src' and return the result string.
/// If src is NULL or maxbytes is 0, return empty string.
/// If maxbytes > src's length, return a duplicate of src.
std::string StringNCopy(const char* src, size_t maxbytes);

/// Return current thread id as a string.
std::string GetTid();

class FdCloser
{
public:
    explicit FdCloser(int fd) : m_fd(fd) {}
    ~FdCloser();

    void Release();

private:
    int m_fd;
};

class FileCloser
{
public:
    FileCloser(FILE* fp) : m_fp(fp) {}
    ~FileCloser() {
        if (m_fp) {
            fclose(m_fp);
            m_fp = nullptr;
        }
    }
private:
    FILE* m_fp;
};

/// <summary> Get the resource limit for number of open files for current process.</summary>
/// Return 0 if infinity, return the actual number othwerwise.
int32_t GetNumFileResourceSoftLimit();

/// <summary>Get syslog severity string from numeric value. E.g., for 5, it's "Notice"</summary>
const char* GetSyslogSeverityStringFromValue(int severity);

/// <summary>
/// Create a UNIX socket using given file path, then bind to it.
/// Throw exception if any error.
/// Return the socket fd.
/// </summary>
int CreateAndBindUnixSocket(const std::string & sockFilePath);

/// <summary>
/// Return the named environment variable value or the default_value if the variable isn't present.
/// If the path specified by the value doesn't exist, throw a runtime_error.
/// </summary>
std::string GetEnvDirVar(const std::string& name, const std::string& default_value);

/// <summary>
/// Parse an absolute https:// or http:// URL in the format of "http(s)://xxx/yyy"
/// Return "http(s)://xxx" as baseUrl, "/yyy" as params.
/// If URL format is "http(s)://xxx", return "http(s)://xxx" as baseUrl, "" as params.
/// Throw exception for invalid format absUrl.
/// </summary>
void ParseHttpsOrHttpUrl(const std::string & absUrl, std::string& baseUrl, std::string& params);

}


#endif // _UTILITY_HH_

// vim: se sw=8
