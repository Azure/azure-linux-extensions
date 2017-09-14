// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTHUBUPLOADER__HH__
#define __EVENTHUBUPLOADER__HH__

#include <string>
#include <queue>
#include <mutex>
#include <atomic>
#include <future>
#include <condition_variable>
#include <memory>

extern "C" {
#include <stddef.h>
}
#include <boost/asio.hpp>
#include "EventData.hh"

namespace boost
{
    namespace system
    {
        class error_code;
    }
}

namespace mdsd
{
    namespace details {
        class EventEntry;
        class EventPersistMgr;
        class EventHubPublisher;
    }
}

namespace mdsd
{

/// <summary>
/// This class implements the functions to upload data to Event Hub service.
/// </summary>
class EventHubUploader
{
    using EventEntryT = std::unique_ptr<details::EventEntry>;

public:
    /// <summary>
    /// Construct an uploader object.
    /// <param name="persistDir">Directory fullpath where failed events are persisted.</param>
    /// <param name="persistResendSeconds">How often to resend failed, persisted events</param>
    /// <param name="memoryTimeoutSeconds">max time to keep data in memory after first failure.</param>
    /// <param name="maxPersistSeconds">Max time to persist failed data.</param>
    /// </summary>
    EventHubUploader(const std::string & persistDir,
                     int32_t persistResendSeconds = 3600,
                     int32_t memoryTimeoutSeconds = 3600,
                     int32_t maxPersistSeconds = 604800  // 7-days
                    );

    ~EventHubUploader();

    /// This class uses 'mutex', which is not movable, not copyable.
    /// So make this class as not movable, not copyable.
    EventHubUploader(const EventHubUploader& other) = delete;
    EventHubUploader(EventHubUploader&& other) = delete;
    EventHubUploader& operator=(const EventHubUploader& other) = delete;
    EventHubUploader& operator=(EventHubUploader&& other) = delete;

    /// <summary>
    /// Set Event Hub SAS Key and start the uploader if not started yet.
    /// When autokey is used, the SAS Key is changed every N hours. This API
    /// will create a new instance of EventHubPublisher. So it should be called only
    /// when SasKey is changed.
    /// NOTE: This API is not thread-safe.
    /// </summary>
    void SetSasAndStart(const std::string & eventHubSas);

    /// <summary>Add data to Event Hub service.</summary>
    void AddData(const EventDataT & data);
    void AddData(EventDataT && data);

    /// <summary>
    /// Wait for given time for all data to be uploaded.
    /// Return until all data are uploaded or timed out.
    /// -1 means forever.
    /// NOTE: this function is not designed for thread-safe. In mdsd, it should
    /// be called sequentially on given EventHubUploader object.
    /// </summary>
    void WaitForFinish(int32_t maxMilliSeconds = -1);

    /// <summary>Get number of success uploads.</summary>
    size_t GetNumUploadSuccess() const { return m_nUpSuccess; }

    /// <summary>Get number of failed uploads.</summary>
    size_t GetNumUploadFail() const { return m_nUpFail; }

    /// <summary>Get number of failed persistence</summary>
    size_t GetNumPersistFail() const { return m_npFail; }

    std::string GetPersistDir() const { return m_persistDir; }

private:
    void WaitForSenderTask(int32_t maxMilliSeconds);
    void ParseEventHubSas(const std::string & eventHubSas,
        std::string& hostUrl, std::string& eventHubUrl, std::string& sasToken);
    void Init();
    void ProcessData(EventEntryT data);
    void Upload();
    void ResendPersistEvents(const boost::system::error_code& error);
    void UploadInterruptionPoint();

private:
    std::shared_ptr<details::EventHubPublisher> m_publisher;
    std::string m_ehSasKey;       // SASKey for EventHub service

    size_t m_nUpSuccess = 0;      // number of upload success
    size_t m_nUpFail = 0;         // number of upload failure
    size_t m_npFail = 0;          // number of persist mgr failure

    int32_t m_memoryTimeoutSeconds; // Max time to keep data in memory after first failure.

    std::queue<EventEntryT> m_uploadQueue; // To store all events in memory.
    std::mutex m_qmutex;                   // For queue/cv synchronization.
    std::condition_variable m_qcv;         // For queue synchronization.

    static const int StopTaskNowMode = 1;          // To stop the sender task immediately.
    static const int StopTaskUntilDoneMode = 2;    // To stop the sender task when all data are processed.

    std::atomic<int> m_stopSenderMode;        // A flag on when to stop the sender task.
    std::future<void> m_senderTask;           // Task to send data to Event Hub service from memory queue.

    int32_t m_persistResendSeconds = 0;               // How often to resend persisted, failed data.
    boost::asio::deadline_timer m_persistResendTimer; // Persisted data resend timer.

    std::string m_persistDir;                          // EventHub data persist dir
    std::shared_ptr<details::EventPersistMgr> m_pmgr; // Event data persistence manager.
    std::once_flag m_initOnceFlag;                    // Once flag to initialize this uploader object.
    bool m_isFinished = false; // Whether EH uploading operation is finished
};

} // namespace mdsd

#endif // __EVENTHUBUPLOADER__HH__
