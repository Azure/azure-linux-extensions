// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _STREAMLISTENER_HH_
#define _STREAMLISTENER_HH_

#include <cstdlib>
#include <cstddef>

#include "Listener.hh"

/// <summary>Listens for JSON-encoded events on a TCP socket</summary>
class StreamListener : public Listener
{
private:
  StreamListener(const StreamListener&);		// Do not define; copy construction forbidden
  StreamListener& operator=(const StreamListener &);	// Ditto for assignment

  char * buffer = nullptr;	// Data received from client
  size_t buflen = 0;	    // Size of buffer
  ptrdiff_t trigger = 0;	// Offset into buffer of leftover data that causes an increase in buffer size
  char * current = nullptr;	// Point at which new data will be added

public:
  StreamListener(int fd) : Listener(fd) {}
  virtual ~StreamListener() { if (buffer) free(buffer); }

  void * ProcessLoop();
};

// vim: set ai sw=2
#endif // _STREAMLISTENER_HH_
