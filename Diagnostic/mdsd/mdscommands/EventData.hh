// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __EVENTDATA_HH__
#define __EVENTDATA_HH__

#include <unordered_map>
#include <string>

namespace mdsd {

/// The EventDataT has 2 parts: a key-value pair table of properties and
/// actual data string.
class EventDataT {
public:
    using EventPropertyT = std::unordered_map<std::string, std::string>;

    EventDataT() = default;
    ~EventDataT() = default;

    bool empty() const { return m_data.empty() && m_table.empty(); }

    std::string GetData() const { return m_data; }
    void SetData(const std::string & data) { m_data = data; }
    void SetData(std::string && data) { m_data = std::move(data); }

    // Specialization for all integral types
    template <typename T>
    typename std::enable_if<std::is_integral<T>::value, void>::type
    AddProperty(std::string name, T value) {
        m_table[std::move(name)] = std::to_string(value);
    }

    void AddProperty(std::string name, std::string value) {
        m_table[std::move(name)] = std::move(value);
    }

    // <summary>
    /// Get properties object which is [key,value] table.
    /// </summary>
    const EventPropertyT & Properties() const {
        return m_table;
    }

    std::string Serialize() const;
    static EventDataT Deserialize(const std::string & datastr);

    /// <summary>
    /// Deserialize a char array and return EventData object.
    /// The memory of the char array must be valid in this function.
    /// </summary>
    static EventDataT Deserialize(const char* buf, size_t bufSize);

    /// <summary>
    /// The max size of EventHub data to support.
    /// </summary>
    static size_t GetMaxSize() { return 256*1024; }

private:
    EventPropertyT m_table; // {key,value} property table
    std::string m_data; // actual message data
};

} // namespace mdsd

#endif // __EVENTDATA_HH__
