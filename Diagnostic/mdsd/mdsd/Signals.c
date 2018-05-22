/*
   Copyright (c) Microsoft Corporation. All rights reserved.
   Licensed under the MIT license.
*/

#define _XOPEN_SOURCE

#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include <execinfo.h>

#define STACK_DEPTH 50

#ifdef DOING_MEMCHECK
extern void RunFinalCleanup();
#endif

extern void LogStackTrace(int, void**, int);
extern void LogAbort();

extern void CatchSigChld(int signo);
extern void CleanupExtensions();
extern void SetCoreDumpLimit();
extern void TruncateAndClosePidPortFile();
extern void StopProtocolListenerMgr();

/* Signals on which we want to backtrace */
static int signalsToBacktrace[] = { SIGSEGV, SIGFPE, SIGILL, SIGTRAP, SIGBUS, SIGSTKFLT, SIGXFSZ };

static int
CatchAndMaskAll(int sig, void(*handler)(int))
{
    struct sigaction sa;
    sa.sa_handler = handler;
    sigfillset(&sa.sa_mask);
    sa.sa_flags = 0;
    return sigaction(sig, &sa, 0);
}

static void
SetBacktraceSignalHandler(void (*backtraceHandler)())
{
    int i;
    for (i = 0; i < sizeof(signalsToBacktrace) / sizeof(int); i++) {
        CatchAndMaskAll(signalsToBacktrace[i], backtraceHandler);
    }
}

static void
ResetBacktraceSignalHandlersToDefault()
{
    int i;
    for (i = 0; i < sizeof(signalsToBacktrace) / sizeof(int); i++) {
        signal(signalsToBacktrace[i], SIG_DFL);
    }
    signal(SIGABRT, SIG_DFL); // We need to reset the SIGABRT handler to default as well, so that our own SIGABRT handler will not be called on this path.
}

void
CatchSigUsr1(int signo)
{
	char msg[] = "In SIGUSR1 handler\n";
	static int FirstTime = 1;
#ifdef DOING_MEMCHECK
	write(2, msg, sizeof(msg));
	if (FirstTime) {
		RunFinalCleanup();
		FirstTime = 0;
		/* Let all registered atexit() handlers run */
		exit(1);
	} else {
		/* What, still here? Die, dang it! */
		_exit(1);
	}
#else
	exit(1);
#endif
}

void
CatchSigUsr2(int signo)
{
    extern void RotateLogs();

    RotateLogs();
}

void
CatchSigHup(int signo)
{
    extern void LoadNewConfiguration();

    LoadNewConfiguration();
}

void
EmitStackTrace(int signo)
{
    void *stack[STACK_DEPTH];
    int count = backtrace(stack, STACK_DEPTH);
    LogStackTrace(signo, stack, count);
}

void
CatchFatal(int signo)
{
    // Code below can easily raise another signal
    // (SIGABRT, most likely), which shouldn't be handled by this handler
    // again, so we have to reset the handler to default. And we do that
    // for all signals on which we may want to dump stack trace.
    ResetBacktraceSignalHandlersToDefault();

    EmitStackTrace(signo);

    CleanupExtensions();

    TruncateAndClosePidPortFile();
}

void
CatchFatalAndExit(int signo)
{
    CatchFatal(signo);
    _exit(signo);
}

void
CatchFatalAndAbort(int signo)
{
    CatchFatal(signo);
    abort();
}

void
CatchTerm(int signo)
{
    CleanupExtensions();
    StopProtocolListenerMgr();

    // The Main thread will exit once ProtocolListenerMgr has stopped.

    /*
    struct sigaction sa_dfl;
    sa_dfl.sa_handler = SIG_DFL;
    sigemptyset(&sa_dfl.sa_mask);
    sa_dfl.sa_restorer = 0;
    sa_dfl.sa_flags = 0;
    sigaction(signo, &sa_dfl, 0);
    raise(signo);
    */
}

void
CatchSigAbort(int signo)
{
    LogAbort();
    // If the SIGABRT signal is ignored, or caught by a handler that returns, the abort() function
    // will still terminate the process. It does this by restoring the default disposition for
    // SIGABRT and then raising the signal for a second time.
}

void BlockSignals()
{
    sigset_t ss;
    sigemptyset(&ss);
    sigaddset(&ss, SIGHUP);
    sigaddset(&ss, SIGALRM);
    sigprocmask(SIG_BLOCK, &ss, NULL);
}

void
SetSignalCatchers(int coreDumpAtFatal)
{
    CatchAndMaskAll(SIGUSR1, CatchSigUsr1);
    CatchAndMaskAll(SIGUSR2, CatchSigUsr2);

    CatchAndMaskAll(SIGINT, CatchTerm);
    CatchAndMaskAll(SIGTERM, CatchTerm);
    CatchAndMaskAll(SIGQUIT, CatchTerm);

    CatchAndMaskAll(SIGHUP, CatchSigHup);

    // SIGABRT shouldn't try to backtrace, because of a glibc bug (https://sourceware.org/bugzilla/show_bug.cgi?id=16159)
    // so catch it with a different handler, where it'll just log the event in mdsd.err and really abort.
    CatchAndMaskAll(SIGABRT, CatchSigAbort);

    void (*backtraceHandler)();
    if (coreDumpAtFatal) {
        SetCoreDumpLimit();
        backtraceHandler = CatchFatalAndAbort;
    }
    else {
        backtraceHandler = CatchFatalAndExit;
    }

    SetBacktraceSignalHandler(backtraceHandler);
    signal(SIGPIPE, SIG_IGN);

    struct sigaction sa_chld;
    sa_chld.sa_handler = CatchSigChld;
    sigemptyset(&sa_chld.sa_mask);
    sa_chld.sa_flags = SA_NOCLDSTOP;
    sigaction(SIGCHLD, &sa_chld, 0);
}
