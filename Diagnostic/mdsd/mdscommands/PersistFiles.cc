// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <fstream>
#include <cstdio>
#include <cstring>
#include <system_error>
#include <vector>

#include <cpprest/filestream.h>
#include <cpprest/containerstream.h>

extern "C" {
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
}

#include "PersistFiles.hh"
#include "MdsCmdLogger.hh"
#include "Trace.hh"
#include "MdsException.hh"
#include "Utility.hh"

using namespace mdsd;
using namespace mdsd::details;

// If the filepath exists and it is a dir, return true;
// otherwise, return false.
static bool
IsDirExists(
    const std::string& filepath
    )
{
    struct stat sb;
    auto rtn = stat(filepath.c_str(), &sb);
    mode_t mode = sb.st_mode;
    return (0 == rtn && S_ISDIR(mode));
}

PersistFiles::PersistFiles(
    const std::string & dirname
    ) :
    m_dirname(dirname),
    m_suffix("XXXXXX"),
    m_fileTemplate(new char[dirname.size()+m_suffix.size()+2])
{
    if (!IsDirExists(m_dirname)) {
        throw MDSEXCEPTION(std::string("Failed to find directory '") + m_dirname + "'.");
    }
    snprintf(m_fileTemplate.get(), dirname.size()+2, "%s/", dirname.c_str());
}

int
PersistFiles::CreateUniqueFile() const
{
    // reset template for mkstemp
    auto offset = m_dirname.size()+1;
    auto sz = m_suffix.size() + 1;
    snprintf(m_fileTemplate.get()+offset, sz, "%s", m_suffix.c_str());

    int fd = mkstemp(m_fileTemplate.get());
    if (-1 == fd) {
        auto errnum = errno;
        std::error_code ec(errnum, std::system_category());
        std::ostringstream strm;
        strm << "Error: creating unique persist file with mkstemp() failed. errno="
            << errnum << "; Reason: " << ec.message();
        MdsCmdLogError(strm);
    }
    return fd;
}

bool
PersistFiles::Add(
    const EventDataT& data
    ) const
{
    if (data.empty()) {
        return true;
    }

    auto fd = CreateUniqueFile();
    if (fd < 0) {
        return false;
    }
    MdsdUtil::FdCloser fdCloser(fd);

    bool resultOK = true;
    auto datastr = data.Serialize();
    if (-1 == write(fd, datastr.c_str(), datastr.size())) {
        std::error_code ec(errno, std::system_category());
        MdsCmdLogError("Error: write() to persist file failed. Reason: "
            + ec.message());
        resultOK = false;
    }

    return resultOK;
}

EventDataT
PersistFiles::Get(
    const std::string& filepath
    ) const
{
    if (filepath.empty()) {
        throw MDSEXCEPTION("Empty string is used for file path parameter.");
    }

    std::ifstream fin(filepath);
    if (!fin) {
        throw MDSEXCEPTION("Failed to open file '" + filepath + "'.");
    }
    fin.seekg(0, fin.end);
    size_t fsize = fin.tellg();
    fin.seekg(0, fin.beg);

    std::vector<char> buf(fsize);
    fin.read(buf.data(), fsize);
    fin.close();

    return EventDataT::Deserialize(buf.data(), fsize);
}

bool
PersistFiles::Remove(
    const std::string& filepath
    ) const
{
    if (filepath.empty()) {
        return true;
    }
    if (remove(filepath.c_str())) {
        std::error_code ec(errno, std::system_category());
        MdsCmdLogError("Error: failed to remove persist file '"
            + filepath + "'. Reason: " + ec.message());
        return false;
    }
    return true;
}

pplx::task<bool>
PersistFiles::RemoveAsync(
    const std::string& filepath
    ) const
{
    Trace trace(Trace::MdsCmd, "PersistFiles::RemoveAsync");

    if (filepath.empty()) {
        return pplx::task_from_result(true);
    }

    return pplx::task<bool>([=]() -> bool {
        return Remove(filepath);
    })
    .then([](pplx::task<bool> previous_task)
    {
        try {
            return previous_task.get();
        }
        catch(std::exception& ex) {
            MdsCmdLogError("PersistFiles::RemoveAsync failed with " + std::string(ex.what()));
        }
        catch(...) {
            MdsCmdLogError("PersistFiles::RemoveAsync failed with unknown exception.");
        }
        return false;
    });
}


int32_t
PersistFiles::GetAgeInSeconds(
    const std::string & filepath
    ) const
{
    struct stat sb;
    auto rtn = stat(filepath.c_str(), &sb);
    if (rtn) {
        std::error_code ec(errno, std::system_category());
        MdsCmdLogError("Error: failed to locate persist file '" + filepath +
            "'. Reason: " + ec.message());
        return -1;
    }
    auto now = time(nullptr);
    return static_cast<int32_t>(now - sb.st_mtime);
}


PersistFiles::const_iterator
PersistFiles::cbegin() const
{
    DirectoryIter diter{m_dirname};
    return diter;
}

PersistFiles::const_iterator
PersistFiles::cend() const
{
    DirectoryIter diter;
    return diter;
}

size_t
PersistFiles::GetNumItems() const
{
    size_t count = 0;
    auto endIter = cend();
    for (auto iter = cbegin(); iter != endIter; ++iter) {
        count++;
    }
    return count;
}

pplx::task<EventDataT>
PersistFiles::GetAsync(
    const std::string & filepath
    ) const
{
    if (filepath.empty()) {
        MdsCmdLogError("Error: GetAsync: unexpected empty filepath.");
        return pplx::task_from_result<EventDataT>(EventDataT());
    }

    return concurrency::streams::file_stream<char>::open_istream(filepath)
    .then([filepath](concurrency::streams::basic_istream<char> inFile)
    {
        if (!inFile.is_open()) {
            MdsCmdLogError("Error: PersistFiles failed to open file '" + filepath + "'.");
            return pplx::task_from_result<EventDataT>(EventDataT());
        }
        else
        {
            concurrency::streams::container_buffer<std::string> buf;
            return inFile.read_to_end(buf)
            .then([inFile, filepath, buf](size_t bytesRead)
            {
                inFile.close();
                if (bytesRead > 0) {
                    return pplx::task_from_result<EventDataT>(EventDataT::Deserialize(buf.collection()));
                }

                MdsCmdLogError("Error: no data is read from '" + filepath + "', unexpected empty file.");
                return pplx::task_from_result<EventDataT>(EventDataT());
            });
        }
    });
}
