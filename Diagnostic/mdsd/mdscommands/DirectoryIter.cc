// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <system_error>
#include <sstream>
#include <cstring>

extern "C" {
#include <sys/types.h>
#include <dirent.h>
}

#include "DirectoryIter.hh"
#include "MdsException.hh"
#include "MdsCmdLogger.hh"

using namespace mdsd::details;

DirectoryIter::DirectoryIter():
    m_dirp(nullptr),
    m_result(nullptr)
{
    memset(&m_ent, 0, sizeof(m_ent));
}

DirectoryIter::DirectoryIter(
    const std::string & dirname):
    m_dirname(dirname),
    m_dirp(nullptr),
    m_result(nullptr)
{
    m_dirp = opendir(dirname.c_str());

    if (!m_dirp) {
        std::error_code ec(errno, std::system_category());
        std::ostringstream strm;
        strm << "Failed to open directory '" << dirname << "'; Reason: " << ec.message();
        throw MDSEXCEPTION(strm.str());
    }

    MoveToNextValid();
}

DirectoryIter::~DirectoryIter()
{
    if (m_dirp) {
        closedir(m_dirp);
    }
}

void
DirectoryIter::MoveToNext()
{
    if (!m_dirp) {
        return;
    }

    auto rtn = readdir_r(m_dirp, &m_ent, &m_result);
    if (rtn) {
        std::ostringstream strm;
        strm << "Error: in directory iteration, readdir_r() failed with error code=" << rtn;
        MdsCmdLogError(strm);
    }
    if (!m_result) {
        memset(&m_ent, 0, sizeof(m_ent));
        closedir(m_dirp);
        m_dirp = nullptr;
        m_result = nullptr;
    }
}

void
DirectoryIter::MoveToNextValid()
{
    while(true) {
        MoveToNext();
        if (!m_dirp) {
            break;
        }

        std::string curdir{m_ent.d_name};
        if ("." != curdir && ".." != curdir) {
            break;
        }
    }
}

DirectoryIter&
DirectoryIter::operator++()
{
    MoveToNextValid();
    return *this;
}

std::string
DirectoryIter::operator*() const {
    if (m_ent.d_name[0]) {
        return m_dirname + "/" + m_ent.d_name;
    }
    else {
        return std::string();
    }
}

bool
mdsd::details::operator==(
    const DirectoryIter& x,
    const DirectoryIter& y
    )
{
    return (x.m_dirp == y.m_dirp &&
            x.m_result == y.m_result &&
            strncmp(x.m_ent.d_name, y.m_ent.d_name, sizeof(x.m_ent.d_name)) == 0);
}
