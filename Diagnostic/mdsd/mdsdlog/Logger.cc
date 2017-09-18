// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Logger.hh"

#include <cstdio>
#include <cerrno>
#include <string>
#include <vector>
#include <iomanip>
#include <thread>
#include <chrono>
#include <system_error>

extern "C" {
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <execinfo.h>
#include <sys/time.h>
#include <sys/uio.h>
}

static void
WriteTimeAndMessage(int fd, const char * timeBuffer, size_t timeLength, const char * message, size_t messageLength)
{
	if (timeBuffer == nullptr || message == nullptr) {
		throw std::invalid_argument("Invalid argument; cannot be nullptr");
	}
	struct iovec iov[4];
	static std::string separator { ": " };
	static char newline = '\n';

	// Deliberately cast the const away. The C++ standard permits this as long as the
	// caller doesn't actually try to change write to the const object. The POSIX
	// standard defines iovec::iov_base as a void* so the struct definition can be
	// shared with readv() and writev().
	iov[0].iov_base = static_cast<void*>(const_cast<char*>(timeBuffer));
	iov[0].iov_len = timeLength;

	iov[1].iov_base = static_cast<void*>(const_cast<char*>(separator.c_str()));
	iov[1].iov_len = separator.length();

	iov[2].iov_base = static_cast<void*>(const_cast<char*>(message));
	iov[2].iov_len = messageLength;

	iov[3].iov_base = static_cast<void*>(&newline);
	iov[3].iov_len = 1;

	ssize_t totalLength = timeLength + separator.length() + messageLength + 1;

	ssize_t result = writev(fd, iov, sizeof(iov)/sizeof(struct iovec));
	if (result == -1) {
		auto saved_errno = errno;
		std::error_code ec(saved_errno, std::system_category());
		std::ostringstream msg;
		msg << "Writev failed: errno " << saved_errno << ": " << ec.message();
		throw std::runtime_error(msg.str());
	} else if (result != totalLength) {
		std::ostringstream msg;
		msg << "Writev() short write: requested " << totalLength << " but wrote " << result;
		throw std::runtime_error(msg.str());
	}
}

size_t
Logger::TimestampISO8601::to_string(struct timeval * tv, char * buffer, size_t buflen)
{
	struct tm zulu;
	size_t totalLength;

	if (!tv || !buffer || !buflen) {
		return 0;
	}

	(void)gmtime_r(&(tv->tv_sec), &zulu);
	totalLength = strftime(buffer, buflen, "%Y-%m-%dT%H:%M:%S", &zulu);
	buffer += totalLength;
	buflen -= totalLength;
	if (buflen < 10) {		// Fractional time won't fit
		return totalLength;
	}

	*buffer++ = '.';
	buflen--;

	auto usec = static_cast<unsigned long>(tv->tv_usec);
	for (int offset = 5; offset >= 0; offset--) {
		if (usec) {
			*(buffer+offset) = '0' + (usec % 10);
			usec /= 10;
		} else {
			*(buffer+offset) = '0';
		}
	}
	buffer += 6;
	buflen -= 6;

	(void)strncpy(buffer, "0Z", buflen-1);

	return totalLength+9;
}

void
Logger::AppendErrnoToMsg(int Error, char * buf, size_t buflen)
{
	char errstrbuf[256];
	char *msg = strerror_r(Error, errstrbuf, 256);

	int offset = strlen(buf);
	snprintf(buf+offset, buflen-offset, "errno %d (%s)", Error, msg);
}

Logger::LogWriter::LogWriter(const char * filename) : m_delay(false)
{
	int tmp_fd = open(filename, O_WRONLY | O_APPEND | O_CREAT, 0755);
	if (tmp_fd < 0) {
		char msgbuf[256];
		snprintf(msgbuf, sizeof(msgbuf), "LogWriter creat failed (errno %d) for path %s", errno, filename);
		msgbuf[255] = 0;	// Just in case filename is too long for the buffer
		m_fd = dup(2);		// Use whatever was stderr
		this->Write(msgbuf);
	} else {
		m_fd = tmp_fd;
		m_filename = filename;
	}
}

Logger::LogWriter::LogWriter() : m_delay(false) { m_fd = dup(2); }

Logger::LogWriter::~LogWriter() { close(m_fd); }

Logger::LogWriter::LogWriter(const LogWriter& orig) : m_filename(orig.m_filename), m_delay(false) { m_fd = dup(orig.m_fd); }
Logger::LogWriter& Logger::LogWriter::operator=(const LogWriter & orig)
{
	if (&orig != this) {
		m_fd = dup(orig.m_fd);
		m_filename = orig.m_filename;
		m_delay = orig.m_delay;
	}
	return *this;
}

int
Logger::LogWriter::Rotate()
{
	if (m_filename.empty()) {
		return -1;
	}

	auto prev_fd = m_fd;
	m_fd = open(m_filename.c_str(), O_WRONLY | O_APPEND | O_CREAT, 0755);
	if (m_fd < 0) {
		m_fd = prev_fd;
		return -1;
	}
	return prev_fd;
}

void Logger::LogWriter::Write(const char * msg, size_t msgLength)
{
	if (!msg) {
		return;
	}

	char timebuffer[100];
	struct timeval tv;
	(void)gettimeofday(&tv, 0);
	size_t timeLength = timestamp->to_string(&tv, timebuffer, sizeof(timebuffer));
	try {
		auto fd = m_fd;
		if (m_delay) {
			std::this_thread::sleep_for(std::chrono::milliseconds(100));
		}
		WriteTimeAndMessage(fd, timebuffer, timeLength, msg, msgLength);
	}
	catch (...)
	{
		// We're screwed; can't log a message if logging throws an exception
	}
}

void Logger::LogWriter::Write(const char * msg)
{
	if (!msg) {
		return;
	}
	Write(msg, strlen(msg));
}

void Logger::LogWriter::Write(const std::string& msg)
{
	Write(msg.c_str(), msg.length());
}

Logger::LogWriter* Logger::errorlog = 0;
Logger::LogWriter* Logger::warnlog = 0;
Logger::LogWriter* Logger::infolog = 0;

std::unique_ptr<Logger::Timestamp> Logger::timestamp = std::unique_ptr<Logger::Timestamp>(new Logger::TimestampISO8601());

void
Logger::Init()
{
	if (!errorlog)
		errorlog = new Logger::LogWriter();
	if (!warnlog)
		warnlog = new Logger::LogWriter();
	if (!infolog)
		infolog = new Logger::LogWriter();

	SetTimestamp(std::unique_ptr<Logger::Timestamp>(new Logger::TimestampISO8601()));
}

void
Logger::Closer::rotate(Logger::LogWriter* log)
{
	if (log) {
		int fd = log->Rotate();
		if (fd >= 0) ToClose.push_back(fd);
	}
}

static void
CloseAfterDelay(std::chrono::duration<int> delaySeconds, std::vector<int> ToClose)
{
	std::this_thread::sleep_for(delaySeconds);
	for (auto fd : ToClose) {
		close(fd);
	}
}

Logger::Closer::~Closer()
{
	if (! ToClose.empty()) {
		std::thread t { CloseAfterDelay, std::chrono::seconds(5), ToClose };
		t.detach();
	}
}

void
Logger::RotateLogs()
{
	Logger::Closer stash;

	stash.rotate(errorlog);
	stash.rotate(warnlog);
	stash.rotate(infolog);
}

void
Logger::EnableDelay()
{
	if (errorlog) errorlog->m_delay = true;
	if (warnlog) warnlog->m_delay = true;
	if (infolog) infolog->m_delay = true;
}

void
Logger::StackTrace(int signo, void **stack, int count)
{
	char buf[256];

	if (errorlog) {
		if (signo > 0) {
			snprintf(buf, sizeof(buf), "FATAL: mdsd killed by signal %d\nStacktrace follows\n===========", signo);
		}
		else {
			snprintf(buf, sizeof(buf), "FATAL: mdsd killed by direct call, no signal involved\nStacktrace follows\n===========");
		}
		errorlog->Write(buf);
		backtrace_symbols_fd(stack, count, errorlog->m_fd);
		errorlog->Write("===========");
	}
}

extern "C" void
LogStackTrace(int signo, void **stack, int count)
{
	Logger::StackTrace(signo, stack, count);
}

extern "C" void
LogAbort()
{
    Logger::LogError("SIGABRT received - immediate exit.");
}

extern "C" void
RotateLogs()
{
	Logger::RotateLogs();
}

// vim: se sw=8 :
