// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <iostream>
#include <sstream>
#include <chrono>
#include <cassert>
extern "C" {
#include <unistd.h>
#include <stddef.h>
}
#include <cpprest/pplx/threadpool.h>
#include <boost/bind.hpp>
#include <boost/algorithm/string/replace.hpp>

#include "EventHubUploader.hh"
#include "MdsException.hh"
#include "MdsCmdLogger.hh"
#include "Trace.hh"
#include "Logger.hh"
#include "EventEntry.hh"
#include "EventPersistMgr.hh"
#include "EventHubPublisher.hh"
#include "Utility.hh"

using namespace mdsd;
using namespace mdsd::details;

class UploadInterruptionException {};

EventHubUploader::EventHubUploader(
    const std::string & persistDir,
    int32_t persistResendSeconds,
    int32_t memoryTimeoutSeconds,
    int32_t maxPersistSeconds
    ) :
    m_publisher(nullptr),
    m_memoryTimeoutSeconds(memoryTimeoutSeconds),
    m_stopSenderMode(0),
    m_persistResendSeconds(persistResendSeconds),
    m_persistResendTimer(crossplat::threadpool::shared_instance().service()),
    m_persistDir(persistDir),
    m_pmgr(EventPersistMgr::create(persistDir, maxPersistSeconds))
{
}

EventHubUploader::~EventHubUploader()
{
    WaitForFinish();
}

void
EventHubUploader::WaitForFinish(
    int32_t maxMilliSeconds
    )
{
    try {
        Trace trace(Trace::MdsCmd, "EventHubUploader::WaitForFinish");
        if (m_isFinished) {
            TRACEINFO(trace, "function is already called. abort.");
            return;
        }
        m_isFinished = true;

        WaitForSenderTask(maxMilliSeconds);

        if (m_senderTask.valid()) {
            m_senderTask.get();
        }
        m_persistResendTimer.cancel();
    }
    catch(std::exception& ex) {
        MdsCmdLogError("Error: EventHubUploader::WaitForFinish failed: " + std::string(ex.what()));
    }
    catch(...) {
        MdsCmdLogError("Error: EventHubUploader::WaitForFinish failed with unknown exception");
    }
}

void
EventHubUploader::SetSasAndStart(
    const std::string & eventHubSas
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploader::SetSasAndStart");
    if (eventHubSas.empty()) {
        MdsCmdLogError("Error: EventHubUploader::SetSasAndStart: unexpected empty EventHub SasKey");
        return;
    }

    if (m_ehSasKey != eventHubSas) {
        std::string hostUrl, eventHubUrl, sasToken;
        ParseEventHubSas(eventHubSas, hostUrl, eventHubUrl, sasToken);

        m_publisher = EventHubPublisher::create(hostUrl, eventHubUrl, sasToken);

        // Because the senderTask requires EH publisher object, so
        // create the task and timer only when EH publisher object is ready.
        // This only needs to be called once.
        std::call_once(m_initOnceFlag, &EventHubUploader::Init, this);

        m_ehSasKey = eventHubSas;
    }
}

void
EventHubUploader::Init()
{
    m_senderTask = std::async(std::launch::async, &EventHubUploader::Upload, this);
    m_persistResendTimer.expires_from_now(boost::posix_time::seconds(m_persistResendSeconds));
    m_persistResendTimer.async_wait(boost::bind(&EventHubUploader::ResendPersistEvents,
                                    this, boost::asio::placeholders::error));
}

void
EventHubUploader::AddData(
    const EventDataT & data
    )
{
    if (data.empty()) {
        return;
    }
    EventDataT dataCopy{data};
    AddData(std::move(dataCopy));
}

void
EventHubUploader::AddData(
    EventDataT && data
    )
{
    if (data.empty()) {
        return;
    }

    EventEntryT item(new EventEntry(std::move(data)));
    std::lock_guard<std::mutex> lk(m_qmutex);
    m_uploadQueue.emplace(std::move(item));
    m_qcv.notify_all();
}

void
EventHubUploader::WaitForSenderTask(
    int32_t milliSeconds
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploader::WaitForSenderTask");

    if (m_stopSenderMode > 0) {
        return;
    }
    if (!m_senderTask.valid()) {
        return;
    }

    TRACEINFO(trace, "Notify sender task to stop ...");

    // Because condition variable (CV)'s checking for predicate and waiting
    // is not atomic, to avoid lost notification, the operations that'll
    // affect predicate results before CV notify() should be protected by
    // the same mutex for CV wait().
    if (-1 == milliSeconds) {
        std::unique_lock<std::mutex> lck(m_qmutex);
        m_stopSenderMode = StopTaskUntilDoneMode;
        m_qcv.notify_all();
        lck.unlock();

        m_senderTask.wait();
    }
    else {
        m_stopSenderMode = StopTaskUntilDoneMode;
        m_senderTask.wait_for(std::chrono::milliseconds(milliSeconds));

        std::unique_lock<std::mutex> lck(m_qmutex);
        auto queueSize = m_uploadQueue.size();
        m_stopSenderMode = StopTaskNowMode;
        m_qcv.notify_all();
        lck.unlock();

        TRACEINFO(trace, "Number of Items in upload queue: " << queueSize );
    }
}

void
EventHubUploader::Upload()
{
    Trace trace(Trace::MdsCmd, "EventHubUploader::Upload");

    try {
        while(StopTaskNowMode != m_stopSenderMode) {
            std::unique_lock<std::mutex> lk(m_qmutex);
            m_qcv.wait(lk, [this] {
                return (m_stopSenderMode || !m_uploadQueue.empty());
            });

            if (m_uploadQueue.empty()) {
                break;
            }
            UploadInterruptionPoint();

            EventEntryT item(std::move(m_uploadQueue.front()));
            m_uploadQueue.pop();
            lk.unlock();

            UploadInterruptionPoint();

            // item could be re-queued based on process result.
            ProcessData(std::move(item));
            UploadInterruptionPoint();
            usleep(500000); // wait for some time to avoid flood azure service.
            UploadInterruptionPoint();
        }
    }
    catch(UploadInterruptionException&) {
        TRACEINFO(trace, "Upload() is interrupted.");
    }
}

void
EventHubUploader::ProcessData(
    EventEntryT item
)
{
    Trace trace(Trace::MdsCmd, "EventHubUploader::ProcessData");

    auto itemAge = item->GetAgeInSeconds();
    std::string itemTag = "Item (";
    itemTag += std::to_string(item->GetId());
    itemTag += ")";

    if (itemAge > m_memoryTimeoutSeconds) {
        TRACEINFO(trace, itemTag << " age (" << itemAge
                << " s) > retry timeout(" << m_memoryTimeoutSeconds << " s). Stop retry.");
        return;
    }

    if (!item->IsTimeToRetry()) {
        std::lock_guard<std::mutex> lk(m_qmutex);
        m_uploadQueue.emplace(std::move(item));
        return;
    }

    UploadInterruptionPoint();

    if(m_publisher->Publish(item->GetData())) {
        m_nUpSuccess++;
        return;
    }

    UploadInterruptionPoint();

    if (item->IsNeverSent()) {
        item->SetSendTime();
    }

    m_nUpFail++;

    // if persist write failed, no backoff. retry as soon as possible.
    bool persistOK = true;
    if (!item->IsInPersistence()) {
        trace.NOTE(itemTag + " upload failed. Add to persist and requeue.");
        persistOK = m_pmgr->Add(item->GetData());
        if (!persistOK) {
            m_npFail++;
            MdsCmdLogError("Error: EventHubUploader data processor failed to add "
                + itemTag + " to persist mgr.");
        }
        else {
            item->SetPersistence();
        }
    }
    else {
        trace.NOTE(itemTag + " failed again. requeue.");
    }

    if (persistOK) {
        trace.NOTE("Backoff " + itemTag);
        item->BackOff();
    }

    UploadInterruptionPoint();
    std::lock_guard<std::mutex> lk(m_qmutex);
    m_uploadQueue.emplace(std::move(item));
}

// input sasKey format: https://tuxtestsb.servicebus.windows.net/Raw?sr=SR&sig=SIG&se=1455131008&skn=writer'
// outputs:
//   - hostUrl: https://tuxtestsb.servicebus.windows.net
//   - eventHubUrl: https://tuxtestsb.servicebus.windows.net/Raw/messages
//   - sasToken: SharedAccessSignature sr=SR&sig=SIG&se=1455131008&skn=writer
void
EventHubUploader::ParseEventHubSas(
    const std::string & eventHubSas,
    std::string & hostUrl,
    std::string & eventHubUrl,
    std::string & sasToken
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploader::ParseEventHubSas");
    std::string prefix{"https://"};
    auto prefixLen = prefix.size();

    if (eventHubSas.compare(0, prefixLen, prefix)) {
        std::ostringstream strm;
        strm << "Invalid Event Hub SAS. SAS is expected to started with '" << prefix << "'";
        throw MDSEXCEPTION(strm.str());
    }
    auto hostPos = eventHubSas.find_first_of('/', prefixLen);
    hostUrl = eventHubSas.substr(0, hostPos);

    auto eventNamePos = eventHubSas.find_first_of('?', hostUrl.size());
    eventHubUrl = eventHubSas.substr(0, eventNamePos) + "/messages";

    auto tmpSasToken = eventHubSas.substr(eventNamePos+1);
    sasToken = MdsdUtil::UnquoteXmlAttribute(tmpSasToken);
    sasToken = "SharedAccessSignature " + sasToken;
}

void
EventHubUploader::ResendPersistEvents(
    const boost::system::error_code& error
    )
{
    Trace trace(Trace::MdsCmd, "EventHubUploader::ResendPersistEvents");
    if (boost::asio::error::operation_aborted == error) {
        trace.NOTE("Previous timer cancelled.");
        return;
    }

    if (!m_pmgr->UploadAllAsync(m_publisher)) {
        MdsCmdLogError(std::string("Error: EventHubUploader failed to start async upload. Retry in ")
            + std::to_string(m_persistResendSeconds) + " seconds.");
    }

    if (0 == m_stopSenderMode) {
        m_persistResendTimer.expires_from_now(boost::posix_time::seconds(m_persistResendSeconds));
        m_persistResendTimer.async_wait(boost::bind(&EventHubUploader::ResendPersistEvents,
                                        this, boost::asio::placeholders::error));
    }
}

void
EventHubUploader::UploadInterruptionPoint()
{
    if (StopTaskNowMode == m_stopSenderMode) {
        throw UploadInterruptionException();
    }
}
