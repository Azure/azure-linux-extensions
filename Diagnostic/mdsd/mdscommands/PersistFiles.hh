// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __PERSISTFILES__HH__
#define __PERSISTFILES__HH__

#include <string>
#include <pplx/pplxtasks.h>
#include "DirectoryIter.hh"
#include "EventData.hh"

namespace mdsd { namespace details
{

class PersistFiles
{
public:
    typedef DirectoryIter const_iterator;

    /// <summary>
    /// Constructor. It will persist files to given directory.
    /// Throw MdsException if it fails to access the directory.
    /// </summary>
    PersistFiles(const std::string & dirname);

    virtual ~PersistFiles() {}

    /// <summary>
    /// Add given data to a new, unique file.
    /// Return true if success, false if any error.
    /// If 'data' is empty, return true and do nothing.
    /// </summary>
    bool Add(const EventDataT& data) const;

    /// <summary>
    /// Get the content of the file given filepath.
    /// Return file content or throw exception if any error.
    /// </summary>
    EventDataT Get(const std::string& filepath) const;

    /// <summary>
    /// Get the content of the file asynchronously given filepath.
    /// Return the task for file content, or task for empty string if any error.
    /// </summary>
    pplx::task<EventDataT> GetAsync(const std::string& filepath) const;

    /// <summary>
    /// Remove a filepath.
    /// Return true if success, false if any error.
    /// </summary>
    bool Remove(const std::string & filepath) const;

    /// <summary>
    /// Remove a filepath asynchronously.
    /// Return true if success, false if any error.
    /// </summary>
    pplx::task<bool> RemoveAsync(const std::string & filepath) const;

    /// <summary>
    /// Get a file's last modification time.
    /// If the file doesn't exit, return -1.
    /// </summary>
    int32_t GetAgeInSeconds(const std::string & filepath) const;

    const_iterator cbegin() const;
    const_iterator cend() const;

    /// <summary>
    /// Get number of items in persist.
    /// </summary>
    size_t GetNumItems() const;

private:
    /// <summary>
    /// Create a unique file. Return an open file descriptor, or -1 if any error.
    /// </summary>
    int CreateUniqueFile() const;

private:
    std::string m_dirname;
    std::string m_suffix;
    std::unique_ptr<char[]> m_fileTemplate;
};

} // namespace details
} // namespace mdsd

#endif // __PERSISTFILES__HH__
