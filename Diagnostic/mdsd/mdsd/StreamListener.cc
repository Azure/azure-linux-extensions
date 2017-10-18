// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

extern "C" {
#include <unistd.h>
#include <pthread.h>
#include <sys/select.h>
}
#include <cerrno>
#include <cctype>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <sstream>

#include "StreamListener.hh"
#include "MdsTime.hh"
#include "Trace.hh"
#include "Utility.hh"

int
ReadFromSocket(int fd, char * buffer, size_t amount)
{
  fd_set readfds;

  while (1) {
    FD_ZERO(&readfds);
    FD_SET(fd, &readfds);
    auto res = select(fd+1, &readfds, 0, 0, 0);
    if (0 == res) {
      // Spurious wakeup; they happen, honest.
      continue;
    }
    if (-1 == res) {
      auto saved_errno = errno;
      throw std::system_error(saved_errno, std::system_category(), "StreamListener select() failed.");
    }

    int len = read(fd, buffer, amount);
    if (-1 == len) {
      // Something unusual happened
      auto saved_errno = errno;
      if (EINTR == errno || EWOULDBLOCK == errno || EAGAIN == errno) {
        continue;
      }
      throw std::system_error(saved_errno, std::system_category(), "StreamListener read() failed.");
    }

    // If we got here, then we read some data or hit eof; either way, we're done
    return len;
  }
}

void *
StreamListener::ProcessLoop()
{
  Trace trace(Trace::EventIngest, "StreamListener::ProcessLoop");

  const int msgbuflen=1024;
  char msgbuf[msgbuflen];

  if (-1 == fcntl(fd(), F_SETFL, O_NONBLOCK)) {
    auto saved_errno = errno;
    Logger::LogError(std::string("StreamListener failed to set O_NONBLOCK: ").append(MdsdUtil::GetErrnoStr(saved_errno)));
    return 0;
  }

  buflen = 256 * 1024;
  trigger = 3 * (buflen>>2);    // 75% full
  buffer = (char *)malloc(buflen + 1);  // Always room to turn "byte array" into "string"
  if (0 == buffer) {
    Logger::LogError("Initial buffer alloc out of memory");
    return(0);
  }
  current = buffer;

  // buffer points to the beginning of the allocated buffer.
  // buflen is the usable size of the buffer (which was allocated with 1 extra byte for a terminal NUL).
  // current points to the location at which we might try to write into the buffer.
  // When the buffer is empty, current==buffer
  // When the buffer is full, current==(buffer+buflen), a valid address at which a single byte can be written.

  while (1) {
    // Invariant: unparsed data in buffer is less than the threshold for expanding the buffer
    auto inuse = current - buffer;    // How far we were in the old buffer

    if (inuse >= trigger) {
      // Sanity check: no legal message is bigger than N MiB
      if (inuse > 4*1024*1024) {
        std::ostringstream msg;
        msg << "Buffered incomplete JSON data (" << inuse << " bytes) exceeds max; probable desync. Buffer head:\n[[";
        msg << MdsdUtil::StringNCopy(buffer, 1024) << "]]\nDropping connection.";
        Logger::LogError(msg.str());
        return(0);
      }

      // Resize the buffer
      TRACEINFO(trace, "Reallocate ingest buffer; was (buflen " << buflen << ", trigger " << trigger << ")");
      if (trace.IsActive() && trace.IsAlsoActive(Trace::IngestContents)) {
        TRACEINFO(trace, "Old buffer start: [[" << MdsdUtil::StringNCopy(buffer, 1024) << "]]");
      }
      buffer = (char *)realloc(buffer, 2 * buflen + 1);
      if (0 == buffer) {
        snprintf(msgbuf, msgbuflen, "Buffer realloc(%ld) out of memory", 2 * buflen + 1);
        Logger::LogError(msgbuf);
        return(0);
      }
      current = buffer + inuse;
      buflen *= 2;
      trigger *= 2;
      TRACEINFO(trace, "Now (buflen " << buflen << ", trigger " << trigger << ")");
    }
    
    int len;
    try {
      len = ReadFromSocket(fd(), current, (buflen - inuse));
    }
    catch (const std::exception& e) {
      Logger::LogError(e.what());
      return 0;
    }

    if (0 == len) {     // End of file - closed socket.
      snprintf(msgbuf, 1024, "End of file on thread %llx - exiting thread", (long long int)pthread_self());
      trace.NOTE(msgbuf);
      return 0;
    }

    // OK, I have some characters. Question is - do I have at least one valid
    // JSON object? Best we can do is guess.
    // If the last character is a backslash, it's not safe to hand the buffer
    // to the parser; if the object is actually incomplete, the backslash will
    // escape the NUL terminator and the parser will go off the edge of the buffer.
    // Did I receive a right-brace in the most recent receive? If not, then
    // I can't possibly have a valid object; go read more.
    // If I saw a right brace, I *might* have a valid object; try to parse it.
    // If I get a NULL back from the parser, I have no valid object; go read more.
    // If I got a valid pointer, then I had at least one valid object, but they've
    // been parsed; the pointer tells me where the next object might begin, so
    // shuffle it to the top of the buffer and go read more.

    const char * cursor = current + len - 1;    // Last character read
    if (*cursor == '\\') {
      // Not safe to parse, and there has to be more coming; go read more.
      current += len;
      continue;
    }
    while (cursor >= current) {
      if (*cursor == '}') break;
      cursor--;
    }
    if (cursor < current) {
      // Nope, can't be an object; go read more.
      current += len;
      continue;
    }

    // Found a right brace. I might have valid objects. Parse the full buffer.
    *(current+len) = '\0';
    try {
      cursor = Listener::ParseBuffer(buffer, current+len);
    }
    catch (const Listener::exception &e) {
      std::ostringstream msg;
      msg << MdsTime() << ": closing connection due to JSON parse error: " << e.what();
      Logger::LogError(msg.str());
      return(0);
    }

    if (0 == cursor) {
      // Nope, no object; go read more.
      current += len;
      continue;
    }

    // OK, processed something. cursor points to the next possible start of object
    // (I can rely on ParseBuffer to have clobbered any trailing whitespace.)
    if (cursor == current+len) {
      current = buffer;         // Processed everything; nothing remains
    } else {
      int delta = current + len - cursor;       // Remaining unprocessed characters
      (void) memmove(buffer, cursor, delta);
      current = buffer + delta;
    }
  }
  /* NOTREACHED */
}

// vim: set ai sw=2 expandtab :
