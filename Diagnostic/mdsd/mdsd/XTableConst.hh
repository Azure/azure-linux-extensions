// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#ifndef _XTABLECONST_HH_
#define _XTABLECONST_HH_

// "Constants" used by XTableSink, DataUploader, etc.
// These are generally run-time constants. They've been encapsulated in this class so they
// can be manipulated at run-time by test code, generally to reduce timeouts or retry counts.

class XTableConstants
{
public:
    // Getters
	static unsigned int BackoffBaseTime()  { return _backoffBaseTime; }
	static unsigned int BackoffLimit()     {return _backoffLimit; }

	static int SDKRetryPolicyInterval() { return _sdkRetryPolicyInterval; }
	static int SDKRetryPolicyLimit()    { return _sdkRetryPolicyLimit; }
	static int InitialOpTimeout()       { return _initialOpTimeout; }
	static int DefaultOpTimeout()       { return _defaultOpTimeout; }

	static unsigned int MaxItemPerBatch() { return 100; }	// Not alterable


    // Setters
	static void SetBackoffBaseTime(unsigned int val) { _backoffBaseTime = val; }
	static void SetBackoffLimit(unsigned int val) { _backoffLimit = val; }

	static void SetSDKRetryPolicyInterval(int val) { _sdkRetryPolicyInterval = val; }
	static void SetSDKRetryPolicyLimit(int val) { _sdkRetryPolicyLimit = val; }
	static void SetInitialOpTimeout(int val) { _initialOpTimeout = val; }
	static void SetDefaultOpTimeout(int val) { _defaultOpTimeout = val; }

private:
	XTableConstants();
	XTableConstants(const XTableConstants&) = delete;

	static unsigned int _backoffBaseTime;
	static unsigned int _backoffLimit;

	static int _sdkRetryPolicyInterval;
	static int _sdkRetryPolicyLimit;
	static int _initialOpTimeout;
	static int _defaultOpTimeout;
};

#endif // _XTABLECONST_HH_

// vim: se sw=8 :
