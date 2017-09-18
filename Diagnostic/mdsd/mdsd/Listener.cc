// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Listener.hh"
#include "Logger.hh"
#include "Engine.hh"
#include "EventJSON.hh"
#include "Trace.hh"
#include "Utility.hh"
#include <cstdlib>
#include <cctype>
#include <sstream>
#include <boost/date_time/posix_time/conversion.hpp>
#include <cpprest/pplx/threadpool.h>

extern "C" {
#include "cJSON.h"
#include <unistd.h>
}

// Set default checkpoint time to 1/2 the default dupe-detection window. The default window
// is one hour.
unsigned int Listener::checkpointSeconds = 60 * 60 / 2;

// Thread startproc. If and when the specific ProcessLoop() method returns, cleanup and exit.
// The pthread interface requires this method to both accept and return a void*.
void *
Listener::handler(void * obj)
{
        Trace trace(Trace::EventIngest, "Listener::handler");

        // Create a shared_ptr to own the Listener object
        auto listener = std::shared_ptr<Listener>((Listener*)obj);

        trace.NOTE("Start timer for " + listener->Name());
        // Start the timer running
        listener->Timer().expires_from_now(boost::posix_time::seconds(checkpointSeconds));
        listener->Timer().async_wait(boost::bind(&Listener::timerhandler, listener, TimerTask::rotate));

        auto result = listener->ProcessLoop();
        trace.NOTE("Returned from ProcessLoop for " + listener->Name());

        listener->Shutdown();

        return result;
}

// Upon receiving an indication from the sender that the session is over, call this method to
// shutdown our end of it. This method should be called synchronously on the listening thread;
// the only expected race is against the timer handler. Once we set _finished, the timer handler
// will do its own cleanup the next time it runs. If the timer handler runs between the moment
// Shutdown sets _finished and the moment it calls _timer.cancel(), we'll be cancelling a timer
// that wasn't set, but that is perfectly fine.
void
Listener::Shutdown()
{
        Trace trace(Trace::EventIngest, "Listener::Shutdown");
        trace.NOTE("Shutting down " + Name());
        close(clientfd);
        _finished = true;
        _timer.cancel();
}

// Parse one or more objects out of a range of characters in the half-open range [start, end).
// Return a pointer to the character immediately following the last object successfully parsed
// (and skipping any trailing whitespace).
// This return value is guaranteed to be <= end. If no message was successfully parsed, a null
// pointer (0) will be returned.
// The parser assumes *end is a NUL byte so it can treat the range as a C string.
const char *
Listener::ParseBuffer(const char* start, const char* end)
{
        Trace trace(Trace::EventIngest, "Listener::ParseBuffer");
        const char * parse_end = 0;
        const char * lkg_parse_end = 0;
        cJSON * event;

        if (*end != '\0') {
                std::ostringstream msg;
                size_t n = end - start + 1;
                msg << "ParseBuffer " << Name() << " got a non-NUL terminated range, length = " << n << "\n";
                DumpBuffer(msg, start, end);
                throw Listener::exception(msg);
        }

        while ((start < end) && (event = cJSON_ParseWithOpts(start, &parse_end, 0))) {
                if (parse_end > end) {
                        std::ostringstream msg;
                        msg << "ParseBuffer found an object longer than the input buffer. Start " << (void *)start << ", end ";
                        msg << (void *)end << ", parse_end " << (void *)parse_end << "\n";
                        if (*end != '\0') {
                                msg << "Range is no longer NUL-terminated.\n";
                        }
                        DumpBuffer(msg, start, end);
                        throw Listener::exception(msg);
                }

                bool status = TryParseEvent(event) || TryParseEcho(event);
                if (!status) {
                        LogBadJSON(event, Name() + " ignored unknown JSON message");
                }

                // Free the parsed event
                cJSON_Delete(event);

                // Advance past the object we just parsed, skip trailing whitespace.
                // I don't really have to do this; cJSON handles leading whitespace. But it's better
                // if I can consume a full buffer; that reduces copying of useless characters.
                while ((parse_end < end) && (isspace(*parse_end))) {
                        parse_end++;
                }
                start = lkg_parse_end = parse_end;
        }
        if (lkg_parse_end != parse_end) {
                TRACEINFO(trace, "parse_end (" << (void*)parse_end << ") != lkg (" << (void*)lkg_parse_end << ")");
        }
        return lkg_parse_end;
}

bool
Listener::TryParseEvent(cJSON* event)
{
    Trace trace(Trace::EventIngest, "Listener::TryParseEvent");

    cJSON* jsTAG = cJSON_GetObjectItem(event, "TAG");
    if (!jsTAG || jsTAG->type != cJSON_String) {
        return false;
    }

    cJSON* jsSOURCE = cJSON_GetObjectItem(event, "SOURCE");
    cJSON* jsDATA = cJSON_GetObjectItem(event, "DATA");
    if ((jsSOURCE && jsSOURCE->type == cJSON_String) && (jsDATA && jsDATA->type == cJSON_Array)) {
        // That's plenty of validation for now.
        if (trace.IsActive()) {
            char *rendering = cJSON_Print(event);
            auto len = strlen(rendering);
            TRACEINFO(trace, "Got event from source " << jsSOURCE->valuestring << " of total size " << len);
            if (trace.IsAlsoActive(Trace::IngestContents)) {
                std::ostringstream msg;
                std::string body(rendering, (len>1024?1024:len));
                msg << Name() << " received JSON event " << body;
                if (len > 1024) {
                    msg << " ... }";
                }
                trace.NOTE(msg.str());
            }
            free(rendering);
        }
        if (IsNewTag(jsTAG)) {
            // Process the event...
            EventJSON evt(event);
            Engine::GetEngine()->ProcessEvent(evt);
        }
        // Inform the client we've processed the event
        EchoTag(jsTAG->valuestring);
    }
    else {
        LogBadJSON(event, Name() + " received incomplete JSON-encoded event");
    }
    return true;
}

bool
Listener::TryParseEcho(cJSON* event)
{
    Trace trace(Trace::EventIngest, "Listener::TryParseEcho");

    cJSON* jsECHO = cJSON_GetObjectItem(event, "ECHO");
    if (jsECHO && jsECHO->type == cJSON_String) {
            EchoTag(jsECHO->valuestring);
            return true;
    }
    return false;
}

void
Listener::LogBadJSON(cJSON* event, const std::string& prefix)
{
        char *rendering = cJSON_Print(event);
        Logger::LogError(prefix + " {" + rendering + "}");
        free(rendering);
}

// Echo the tag, followed by a newline, back to the client.
void
Listener::EchoTag(char * tagptr)
{
        try {
                MdsdUtil::WriteBufferAndNewline(clientfd, tagptr);
        }
        catch (const MdsdUtil::would_block& e) {
                std::ostringstream msg;
                msg << "Event source tag-reader is slow; dropping tag " << tagptr;
                Logger::LogWarn(msg);
        }
        catch (const std::system_error& e) {
                if (EPIPE == e.code().value()) {
                        throw Listener::exception(std::string("Event sender closed connection: ") + e.what());
                }
                else {
                        Logger::LogError(std::string("Listener failed to echo TAG: ") + e.what());
                }
        }
        catch (const std::runtime_error& e) {
                Logger::LogError(std::string("Listener failed to echo TAG: ") + e.what());
        }
}

Listener::Listener(int fd) : clientfd(fd),
                tagsAgedOut(0), tagsOldest(new tag_set()), tagsOld(new tag_set()), tagsCurr(new tag_set()),
                _timer(crossplat::threadpool::shared_instance().service()), _finished(false)
{
        Trace trace(Trace::EventIngest, "Listener::Listener");

        std::ostringstream msg;
        msg << this;
        _name = msg.str();

        trace.NOTE("Constructed Listener " + Name());
}

Listener::~Listener()
{
        Trace trace(Trace::EventIngest, "Listener::~Listener");

        Logger::LogWarn("Closing fd in ~Listener()");
        trace.NOTE("Destroying Listener " + Name());
        close(clientfd);
        if (tagsAgedOut) {
                delete tagsAgedOut;
                tagsAgedOut = 0;
        }
        if (tagsOldest) {
                delete tagsOldest;
                tagsOldest = nullptr;
        }
        if (tagsOld) {
                delete tagsOld;
                tagsOld = nullptr;
        }
        if (tagsCurr) {
                delete tagsCurr;
                tagsCurr = nullptr;
        }
}

bool Listener::IsNewTag(cJSON* jsTAG)
{
        Trace trace(Trace::EventIngest, "Listener::IsNewTag");
        if (nullptr == jsTAG)
        {
                trace.NOTE("Got a NULL JSON object pointer");
                return false;
        } else if (nullptr == jsTAG->valuestring) {
                trace.NOTE("JSON object had NULL valuestring");
                return false;
        } else if (0 == *(jsTAG->valuestring)) {
                trace.NOTE("JSON object had zero-length valuestring");
                return false;
        }

        trace.NOTE("Checking tag \"" + std::string(jsTAG->valuestring) + "\"");

        bool isNewTag = true;
        std::string tagstr(jsTAG->valuestring);

        // Capture the tag sets to check. We're racing against the timer handler which will
        // rotate the grandparent to great-grandparent, parent to grandparent, current to
        // parent, and an empty set into current. When we capture current/parent/grand during
        // the rotation operation, we might wind up with empty/current/parent or
        // current/current/parent or current/parent/parent, but since we're checking right
        // on the "rotation" time, the relevant time window really does encompass just current
        // and parent at the instant we start looking. We might wind up checking a tag set
        // twice, but we won't segfault and we won't miss checking a relevant tag set.

        auto currentSet = tagsCurr;
        auto parentSet = tagsOld;
        auto grandparentSet = tagsOldest;

        if (currentSet->end() != currentSet->find(tagstr) ||
                parentSet->end() != parentSet->find(tagstr) ||
                grandparentSet->end() != grandparentSet->find(tagstr))
        {
                isNewTag = false;
                trace.NOTE("Tag is a duplicate");
        }
        else
        {
                // Yes, I really mean tagsCurr. If rotation happened between the time this
                // thread grabbed the set pointers and now, currentSet points to tagsOld, so
                // putting this tag into currentSet might leave the tag active for just a hair
                // less than the guaranteed interval. Better too long than too short.
                tagsCurr->insert(tagstr);
                trace.NOTE("Tag is new");
        }

        return isNewTag;
}

void
Listener::RotateTagSets()
{
        Trace trace(Trace::EventIngest, "Listener::RotateTagSets");

        if (trace.IsActive())
        {
                std::ostringstream msg;
                msg << Name() << " Tagset sizes: Curr=" << tagsCurr->size() << "; Old=" << tagsOld->size();
                msg << "; Oldest=" << tagsOldest->size();
                trace.NOTE(msg.str());
        }

        tagsAgedOut = tagsOldest;
        tagsOldest = tagsOld;
        tagsOld = tagsCurr;
        tagsCurr = new tag_set();
}

void
Listener::ScrubTagSets()
{
        Trace trace(Trace::EventIngest, "Listener::ScrubTagSets");

        if (tagsAgedOut) {
                if (trace.IsActive()) {
                        std::ostringstream msg;
                        msg << Name() << " releasing " << tagsAgedOut->size() << " tags";
                        trace.NOTE(msg.str());
                }
                delete tagsAgedOut;
                tagsAgedOut = 0;
        }
}

void
Listener::timerhandler(std::shared_ptr<Listener> listener, Listener::TimerTask job)
{
        Trace trace(Trace::EventIngest, "Listener::timerhandler");

        if (listener->IsFinished()) {
                // Do nothing; especially, do not reschedule the timer. The deadline_timer code
                // will allow its copy of the shared_ptr for this instance to go out of scope,
                // triggering a safe delete of the Listener class instance. If we were cancelled,
                // we'll want to do exactly the same thing, and Listener::handler is careful to set
                // _socketClosed before it tries to cancel the timer. As a result, there's no need
                // to check to see if we're being cancelled or not; if _socketClosed is set,
                // just return.
                trace.NOTE(listener->Name() + " IsFinished is true");
                return;
        }

        switch (job) {
        case TimerTask::rotate:
                listener->RotateTagSets();
                listener->Timer().expires_from_now(boost::posix_time::seconds(15));
                listener->Timer().async_wait(boost::bind(&Listener::timerhandler, listener, TimerTask::cleanup));
                break;

        case TimerTask::cleanup:
                listener->ScrubTagSets();
                listener->Timer().expires_from_now(boost::posix_time::seconds(checkpointSeconds - 15));
                listener->Timer().async_wait(boost::bind(&Listener::timerhandler, listener, TimerTask::rotate));
                break;

        default:
                Logger::LogError("Listener::timerhandler saw unexpected state " + std::to_string(job));
                listener->Timer().expires_from_now(boost::posix_time::seconds(checkpointSeconds));
                listener->Timer().async_wait(boost::bind(&Listener::timerhandler, listener, TimerTask::rotate));
                break;
        }
}

void
Listener::DumpBuffer(std::ostream& os, const char* start, const char* end)
{
        size_t n = end - start + 1;
        if (n < 1024*1024) {
                os << "Buffer contents [" << std::string(start, n) << "]";
        } else {
                os << "Partial buffer contents [" << std::string(start, 1024*1024) << "]";
        }
}

// vim: set ai sw=8 expandtab :
