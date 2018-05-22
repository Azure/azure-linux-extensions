// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _LOGGER_HH_
#define _LOGGER_HH_

#include <cstring>
#include <string>
#include <sstream>
#include <vector>
#include <memory>

struct timeval;

class Logger
{
public:
	class Timestamp {
	public:
		Timestamp() {}
		virtual ~Timestamp() {}
		virtual size_t to_string(struct timeval * tv, char * buffer, size_t buflen) = 0;
	};
	class TimestampISO8601 : public Timestamp {
	public:
		virtual size_t to_string(struct timeval * tv, char * buffer, size_t buflen);
	};
private:
	class Closer;
	class LogWriter {

	friend class Logger;
	friend class Logger::Closer;

	private:
		int m_fd;
		std::string m_filename;
		bool m_delay;

	public:
		LogWriter(const char * filename);
		LogWriter();

		~LogWriter();

		LogWriter(const LogWriter& orig);
		LogWriter& operator=(const LogWriter & orig);

		/// <summary>Write a message to a logfile</summary>
		/// <param name="msg">The message to be written</param>
		void Write(const char * msg);
		/// <summary>Write a message to a logfile</summary>
		/// <param name="msg">The message to be written</param>
		/// <param name="len">The length of message</param>
		void Write(const char * msg, size_t len);
		/// <summary>Write a message to a logfile</summary>
		/// <param name="msg">The message to be written</param>
		void Write(const std::string& msg);

		int Rotate();
	};

        class Closer
        {
        public:
                void rotate(Logger::LogWriter* log);
                ~Closer();
        private:
                std::vector<int> ToClose;
        };

	static LogWriter * errorlog;
	static LogWriter * warnlog;
	static LogWriter * infolog;

	static std::unique_ptr<Timestamp> timestamp;

	Logger();

public:
	static void Init();

	static void LogError(const char * msg) { if (errorlog) errorlog->Write(msg); }
	static void LogWarn(const char * msg) { if (warnlog) warnlog->Write(msg); }
	static void LogInfo(const char * msg) { if (infolog) infolog->Write(msg); }

	/// <summary>Write a message to the error logfile</summary>
	/// <param name="msg">The message to be written</param>
	static void LogError(const std::string& msg) { if (errorlog) errorlog->Write(msg); }
	static void LogError(const std::ostringstream& msg) { if (errorlog) LogError(msg.str()); }
	static void LogWarn(const std::string& msg) { if (warnlog) warnlog->Write(msg); }
	static void LogWarn(const std::ostringstream& msg) { if (warnlog) LogWarn(msg.str()); }
	static void LogInfo(const std::string& msg) { if (infolog) infolog->Write(msg); }
	static void LogInfo(const std::ostringstream& msg) { if (infolog) LogInfo(msg.str()); }

	static void StackTrace(int signo, void **stack, int count);

	static void SetErrorLog(const char * pathname) { delete errorlog; errorlog = new LogWriter(pathname); }
	static void SetWarnLog(const char * pathname) { delete warnlog; warnlog = new LogWriter(pathname); }
	static void SetInfoLog(const char * pathname) { delete infolog; infolog = new LogWriter(pathname); }

	static void CloseAllLogs() { delete errorlog; delete warnlog; delete infolog; errorlog = warnlog = infolog = nullptr; }

	static void AppendErrnoToMsg(int Error, char * buf, size_t buflen);

	static void SetTimestamp(std::unique_ptr<Timestamp> && timestamp_) { timestamp = std::move(timestamp_); }

	static void RotateLogs();
	static void EnableDelay();
};

#endif //_LOGGER_HH_

// vim: set ai sw=8 :
