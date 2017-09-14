// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <cassert>
extern "C" {
#include <unistd.h>
}
#include "EventPersistMgr.hh"
#include "MdsCmdLogger.hh"
#include "Trace.hh"
#include "PersistFiles.hh"
#include "EventHubPublisher.hh"
#include "Utility.hh"

using namespace mdsd::details;


EventPersistMgr::EventPersistMgr(
    const std::string & persistDir,
    int32_t maxKeepSeconds
    ) :
    m_dirname(persistDir),
    m_persist(new PersistFiles(persistDir)),
    m_maxKeepSeconds(maxKeepSeconds),
    m_nFileProcessed{0}
{
}

EventPersistMgr::~EventPersistMgr()
{
}

bool
EventPersistMgr::Add(
    const EventDataT & data
    )
{
    if (data.empty()) {
        return true;
    }
    try {
        return m_persist->Add(data);
    }
    catch(std::exception & ex) {
        MdsCmdLogError(std::string("Error: adding data to persistence hit exception: ") + ex.what());
    }
    return false;
}

size_t
EventPersistMgr::GetNumItems() const
{
    return m_persist->GetNumItems();
}

bool
EventPersistMgr::UploadAllSync(
    std::shared_ptr<EventHubPublisher> publisher
    ) const
{
    Trace trace(Trace::MdsCmd, "EventPersistMgr::UploadAllSync");

    if (!publisher) {
        MdsCmdLogError("Error: EventPersistMgr::UploadAllSync(): unexpected NULL for publisher object.");
        return false;
    }

    int nPubErrs = 0;
    auto endIter = m_persist->cend();
    for (auto iter = m_persist->cbegin(); iter != endIter; ++iter)
    {
        auto item = *iter;
        auto ageInSeconds = m_persist->GetAgeInSeconds(item);
        assert(ageInSeconds >= 0);

        if (ageInSeconds >= m_maxKeepSeconds) {
            m_persist->Remove(item);
        }
        else {
            try {
                auto itemdata = m_persist->Get(item);
                if (publisher->Publish(itemdata)) {
                    m_persist->Remove(item);
                }
                else {
                    nPubErrs++;
                }
            }
            catch(std::exception & ex) {
                MdsCmdLogError(std::string("Error: EventPersistMgr UploadAllSync() hits exception: ") + ex.what());
                nPubErrs++;
            }
            usleep(100000); // sleep some time to avoid flush azure service.
        }
    }
    if (nPubErrs) {
        std::ostringstream strm;
        strm << "Error: EventPersistMgr UploadAllSync() hit " << nPubErrs << " publication errors.";
        MdsCmdLogError(strm);
    }
    return (0 == nPubErrs);
}

// Check whether an I/O error is retryable.
// NOTE: this list may need to to be adjusted based on actual errors found in the future.
// They are obtained from 'man 2 open', 'man 2 read', 'man 2 close'.
static inline bool
IsFileIOErrorRetryable(int errcode)
{
    switch(errcode) {
        case EACCES:
        case EISDIR:
        case ELOOP:
        case ENAMETOOLONG:
        case ENOTDIR:
        case EOVERFLOW:
        case EIO:
            return false;
        default:
            return true;
    }
    return true;
}

/// <summary>
/// A convenient helper function to loop asychronously until a condition is met.
/// NOTE: These functions are from CPPREST sample code.
/// </summary>
pplx::task<bool> _do_while_iteration(std::function<pplx::task<bool>(void)> func)
{
    pplx::task_completion_event<bool> ev;
    func().then([=](bool guard)
    {
        ev.set(guard);
    });
    return pplx::create_task(ev);
}
pplx::task<bool> _do_while_impl(std::function<pplx::task<bool>(void)> func)
{
    return _do_while_iteration(func).then([=](bool guard) -> pplx::task<bool>
    {
        if(guard)
        {
            return ::_do_while_impl(func);
        }
        else
        {
            return pplx::task_from_result(false);
        }
    });
}
pplx::task<void> do_while(std::function<pplx::task<bool>(void)> func)
{
    return _do_while_impl(func).then([](bool){});
}

std::shared_ptr<std::queue<std::string>>
EventPersistMgr::GetAllFiles() const
{
    auto fqueue = std::make_shared<std::queue<std::string>>();

    auto endIter = m_persist->cend();
    for (auto iter = m_persist->cbegin(); iter != endIter; ++iter)
    {
        auto item = *iter;
        auto ageInSeconds = m_persist->GetAgeInSeconds(item);
        assert(ageInSeconds >= 0);

        if (ageInSeconds >= m_maxKeepSeconds) {
            m_persist->RemoveAsync(item);
        }
        else {
            fqueue->push(item);
        }
    }
    return fqueue;
}

static std::shared_ptr<std::queue<std::string>>
CreateBatch(
    std::shared_ptr<std::queue<std::string>> fullList,
    size_t batchSize
    )
{
    if (fullList->size() <= batchSize) {
        return fullList;
    }

    auto batch = std::make_shared<std::queue<std::string>>();
    for (size_t i = 0; i < batchSize; i++) {
        if (fullList->empty()) {
            break;
        }
        batch->push(fullList->front());
        fullList->pop();
    }
    return batch;
}

static void
HandlePrevTaskFailure(
    pplx::task<void> previous_task,
    const std::string & testname
    )
{
    try {
        previous_task.wait();
    }
    catch(const std::exception& ex) {
        MdsCmdLogError(testname + " has exception: " + ex.what());
    }
    catch(...) {
        MdsCmdLogError(testname + " has unknown exception.");
    }
}

// Calculate how many batches to use and each batch's size
// based on total items to process and max open file resource limit.
//
// Make sure maxBatches is used.
//
// The result is that totalItems can be divided into n batches, such that
// the first nExtraOne batches have batchSize+1 items, the rest
// (nbatches-nExtraOne) has batchSize items.
// e.g. totalItems=7, maxBatches=5, we want to have (2,2,1,1,1), where
// nbatches=5, batchSize=1, nExtraOne=2.
static void
CalcBatchInfo(
    size_t totalItems,
    size_t& nbatches,
    size_t& batchSize,
    size_t& nExtraOne
    )
{
    Trace trace(Trace::MdsCmd, "EventPersistMgr::CalcBatchInfo");

    auto fdLimit = MdsdUtil::GetNumFileResourceSoftLimit();

    if (0 == fdLimit) {
        // max open file is unlimited, each batch processes one file.
        nbatches = totalItems;
        batchSize = 1;
        nExtraOne = 0;
    }
    else {
        // max batches: 10% of max open files.
        // so that we won't run out of open files.
        size_t maxBatches = fdLimit / 10;

        nbatches = std::min(totalItems, maxBatches);
        batchSize = totalItems / nbatches;
        nExtraOne = totalItems % nbatches;
    }

    assert((nbatches*batchSize+nExtraOne) == totalItems);

    TRACEINFO(trace, "total=" << totalItems << "; nbatches=" << nbatches <<
        "; batchSize=" << batchSize << "; nExtraOne=" << nExtraOne);
}

bool
EventPersistMgr::UploadAllAsync(
    std::shared_ptr<EventHubPublisher> publisher
    ) const
{
    Trace trace(Trace::MdsCmd, "EventPersistMgr::UploadAllAsync");

    if (!publisher) {
        MdsCmdLogError("Error: EventPersistMgr::UploadAllAsync(): unexpected NULL for publisher object.");
        return false;
    }

    auto allFileList = GetAllFiles();
    if (allFileList->empty()) {
        return true;
    }
    auto nFilesToProcess = allFileList->size();
    size_t nbatches = 0;
    size_t batchSize = 0;
    size_t nExtraOne = 0;
    CalcBatchInfo(nFilesToProcess, nbatches, batchSize, nExtraOne);

    auto shThis = shared_from_this();

    size_t nFilesInBatch = 0;
    for (size_t i = 0; i < nbatches; i++) {
        auto nItems = (i < nExtraOne)? (batchSize+1) : batchSize;
        auto batch = CreateBatch(allFileList, nItems);

        nFilesInBatch += batch->size();
        pplx::task<void>([shThis, publisher, batch]()
        {
            shThis->UploadFileBatch(publisher, batch);
        });
    }

    assert(nFilesInBatch == nFilesToProcess);

    return true;
}

// This function will process a list of files by using
// one open file handle only. It uses the async task idiom 'do_while'
// to process these files in an async task loop.
void
EventPersistMgr::UploadFileBatch(
    std::shared_ptr<EventHubPublisher> publisher,
    std::shared_ptr<std::queue<std::string>> flist
    ) const
{
    if (flist->empty()) {
        return;
    }

    auto shThis = shared_from_this();

    ::do_while([shThis, flist, publisher]()
    {
        if (flist->empty()) {
            return pplx::task_from_result(false);
        }
        auto fileItem = flist->front();
        flist->pop();
        return shThis->UploadOneFile(publisher, fileItem);
    })
    .then([](pplx::task<void> previous_task)
    {
        HandlePrevTaskFailure(previous_task, "UploadFileBatch");
    });
}

pplx::task<bool>
EventPersistMgr::UploadOneFile(
    std::shared_ptr<EventHubPublisher> publisher,
    const std::string & filePath
    ) const
{
    auto shThis = shared_from_this();

    return m_persist->GetAsync(filePath)
    .then([publisher, shThis, filePath](const EventDataT & fileData)
    {
        shThis->ProcessFileData(publisher, filePath, fileData);
    })
    .then([shThis, filePath](pplx::task<void> previous_task)
    {
        shThis->m_nFileProcessed++;
        shThis->HandleReadTaskFailure(previous_task, filePath);
        return true;
    });
}

void
EventPersistMgr::ProcessFileData(
    std::shared_ptr<EventHubPublisher> publisher,
    const std::string & item,
    const EventDataT & itemdata
    ) const
{
    if (itemdata.empty()) {
        return;
    }

    auto shThis = shared_from_this();
    publisher->PublishAsync(itemdata)
    .then([publisher, shThis, item](bool publishOK)
    {
        if (publishOK) {
            shThis->m_persist->RemoveAsync(item)
            .then([item](bool removeOK) {
                if (!removeOK) {
                    MdsCmdLogError("Error: EventPersistMgr::ProcessFileData failed to remove file " +
                        MdsdUtil::GetFileBasename(item));
                }
            });
        }
        else {
            MdsCmdLogError("Error: EventPersistMgr::ProcessFileData failed to upload file " +
                MdsdUtil::GetFileBasename(item));
        }
    })
    .then([item](pplx::task<void> previous_task)
    {
        try {
            previous_task.wait();
        }
        catch(const std::exception& ex) {
            MdsCmdLogError("Error: failed to publish EH file " + MdsdUtil::GetFileBasename(item) +
                ". Exception: " + std::string(ex.what()));
        }
        catch(...) {
            MdsCmdLogError("Error: failed to publish EH file " + MdsdUtil::GetFileBasename(item) +
                " with unknown exception.");
        }
    });
}

void
EventPersistMgr::HandleReadTaskFailure(
    pplx::task<void> readTask,
    const std::string & item
    ) const
{
    try {
        readTask.wait();
    }
    catch(const std::system_error & ex) {
        auto ec = ex.code().value();

        if (IsFileIOErrorRetryable(ec)) {
            MdsCmdLogWarn("Warning: failed to publish EH file " + MdsdUtil::GetFileBasename(item) +
                ". Exception: " + std::string(ex.what()) + ". Retry next time.");
        }
        else {
            MdsCmdLogError("Error: failed to publish EH file " + MdsdUtil::GetFileBasename(item) +
                ". Exception: " + std::string(ex.what()) + ". Remove file.");
            m_persist->RemoveAsync(item);
        }
    }
    catch(const std::exception& ex) {
        // To be conservative: for exception without details, retry them later.
        MdsCmdLogError("Error: failed to publish EH file " + MdsdUtil::GetFileBasename(item) +
            ". Exception: " + std::string(ex.what()) + ". Retry next time.");
    }
    catch(...) {
        MdsCmdLogError("Error: failed to publish EH file " + MdsdUtil::GetFileBasename(item) +
            " with unknown exception.");
    }
}

// vim: sw=4 expandtab :
