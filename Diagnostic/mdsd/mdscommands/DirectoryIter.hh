// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __DIRECTORYITER__HH__
#define __DIRECTORYITER__HH__

#include <string>
extern "C" {
#include <dirent.h>
}

namespace mdsd { namespace details
{

/// <summary>
/// Iterator each entry in the directory, including sub-directories.
/// It ignores "." and "..".
/// </summary>
class DirectoryIter
{
public:
    /// <sumamry>A directory iterator pointing to nothing </summary>
    DirectoryIter();
    /// <summary>A directory iterator for given dir</summary>
    DirectoryIter(const std::string & dirname);
    ~DirectoryIter();

    /// There is no safe way to copy 'DIR*'. Make class movable, not copyable.
    DirectoryIter(const DirectoryIter& other) = delete;
    DirectoryIter(DirectoryIter&& other) = default;
    DirectoryIter& operator=(const DirectoryIter& other) = delete;
    DirectoryIter& operator=(DirectoryIter&& other) = default;

    /// <summary> Pre-increment operator. Move to next entry in the directory.</summary>
    DirectoryIter& operator++();

    /// <summary> Return current item name (filename or dir name) </summary>
    std::string operator*() const;

    /// <summary> Return whether 2 iter points to the same thing </summary>
    friend bool operator==(const DirectoryIter& x, const DirectoryIter& y);

    /// <summary> Return whether 2 iter points to different things </summary>
    friend bool operator!=(const DirectoryIter& x, const DirectoryIter& y)
    {
        return !(x==y);
    }

private:
    void MoveToNext();
    void MoveToNextValid();

private:
    std::string m_dirname;
    DIR* m_dirp;
    struct dirent m_ent;
    struct dirent * m_result;
};

bool operator==(const DirectoryIter& x, const DirectoryIter& y);

} // namespace details
} // namespace mdsd

#endif // __DIRECTORYITER__HH__
