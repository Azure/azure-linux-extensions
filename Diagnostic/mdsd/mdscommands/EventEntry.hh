// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once

#ifndef __EVENTENTRY_HH__
#define __EVENTENTRY_HH__

#include <string>
#include <ctime>
#include <atomic>
#include "EventData.hh"

namespace mdsd { namespace details
{
/// <summary>
/// EventEntry class include data sent to EventHub for each upload,
/// plus some metadata about the event data.
/// <summary>
class EventEntry
{
public:
    EventEntry(const EventDataT & data) :
        m_rawData(data)
    {
        s_counter++;
        m_id = s_counter;
    }

    EventEntry(EventDataT && data) :
        m_rawData(std::move(data))
    {
        s_counter++;
        m_id = s_counter;
    }

    ~EventEntry() {}

    EventEntry(const EventEntry& other) = default;
    EventEntry(EventEntry&& other) = default;
    EventEntry& operator=(const EventEntry& other) = default;
    EventEntry& operator=(EventEntry&& other) = default;

    /// <summary>Do exponential backoff for next retry </summary>
    void BackOff()
    {
        auto delta = m_nextSendTimet - m_firstSendTimet;
        if (0 == delta) {
            m_nextSendTimet++;
        }
        else {
            m_nextSendTimet = m_firstSendTimet + delta*2 + 1;
        }
    }

    bool IsNeverSent() const { return (0 == m_firstSendTimet); }

    void SetSendTime()
    {
        auto now = GetNow();
        m_firstSendTimet = now;
        m_nextSendTimet = now;
    }

    /// <summary>
    /// Get number of seconds since the data was first uploaded.
    /// Return -1 if the data is never uploaded before.
    /// </summary>
    int32_t GetAgeInSeconds() const
    {
        if (0 == m_firstSendTimet) {
            return -1;
        }
        return (GetNow() - m_firstSendTimet);
    }

    EventDataT GetData() const { return m_rawData; }

    /// <summary> Get some ID for the event, for tracing purpose only.
    /// no need to be unique. </summary>
    uint64_t GetId() const { return m_id; }

    /// <summary> Is it now the time to re-upload the data? </summary>
    bool IsTimeToRetry() const { return (GetNow() >= m_nextSendTimet); }

    bool IsInPersistence() const { return m_inPersistence; }
    void SetPersistence() { m_inPersistence = true; }

private:
    time_t GetNow() const { return time(nullptr); }

private:
    // The minimum time to upload when getting a next chance.
    // If the current time is less than this value, data won't be uploaded.
    time_t m_nextSendTimet = 0;

    time_t m_firstSendTimet = 0;   // The first time to upload the data.
    EventDataT m_rawData;         // The raw data uploaded to Event Hub.
    static std::atomic<uint64_t> s_counter;
    uint64_t m_id = 0;             // A ID for the entry. For tracing purpose only.
    bool m_inPersistence = false;  // Is the item added to persistence manager?
};

} // namespace details
} // namespace mdsd

#endif // __EVENTENTRY_HH__
