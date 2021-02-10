// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _XJSONBLOBSINK_HH_
#define _XJSONBLOBSINK_HH_

#include "IMdsSink.hh"
#include <string>
#include "MdsTime.hh"
#include "MdsEntityName.hh"
#include <memory>
#include <mutex>
#include <condition_variable>

class CanonicalEntity;
class Credentials;
class MdsdConfig;
class MdsValue;
class XJsonBlobRequest;
namespace mdsd {
	struct OboDirectConfig;
}
namespace azure { namespace storage {
    class block_list_item;
}}


// Thin object wrapper, supporting synchronization across async task threads (with owner name)
template <typename T>
class ObjectWithOwnership
{
public:
    ObjectWithOwnership() {}

    T& get() { return _object; }

    void LockIfOwnedByNoneThenSetOwner(const std::string& ownerName)
    {
        if (ownerName.empty()) {
            throw std::invalid_argument("Passed ownerName is empty in ObjectWithOwnership::LockIfOwnedByNoneThenSetOwner");
        }

        std::unique_lock<std::mutex> lock(_mutex);
        _cv.wait(lock, [this]{ return _ownerName.empty(); });
        _ownerName = ownerName;
    }

    // Caller must make sure that the set owner is itself.
    void ResetOwnerAndNotify()
    {
        std::lock_guard<std::mutex> lock(_mutex);

        if (_ownerName.empty()) {
            throw std::runtime_error("Current _ownerName is empty in ObjectWithOwnership::ResetOwnerAndNotify");
        }

        _ownerName.clear();
        _cv.notify_all();
    }

private:
    T _object;
    std::mutex _mutex;
    std::string _ownerName;
    std::condition_variable _cv;
};


using BlockListT = ObjectWithOwnership<std::vector<azure::storage::block_list_item>>;


class XJsonBlobSink : public IMdsSink
{
public:

    struct RequestInfo
    {
    public:
        const MdsEntityName target;		// Destination storage container
        std::string primaryPartitionField;
            // E.g., "resourceId=...". 'resourceId' is obtained from OboDirectConfig.primaryPartitionField,
            // and '...' needs to be obtained from somewhere else (Portal/LAD config? -- WAD is blocked on this)
        std::string agentIdentityHash;
        std::string partitionFields;
            // E.g., "resourceId=xxx/subscriptionId=yyy". 'resourceId' and 'subscriptionId' are obtained from OboDirectConfig.partitionFields,
            // and 'xxx' and 'yyy' need to be obtained from somewhere else (OBO service? What about LAD scenario?)
        std::string duration;	// E.g., "PT1M" for metric events. "" for non-metric events. Will be used by Json construction

        std::string tenant;	// Tenane name in metric Json content
        std::string role;   // Role name in metric Json content
        std::string roleInstance; // RoleInstance name in metric Json content

        RequestInfo(const MdsEntityName& t) : target(t) {}
    };

    virtual bool IsXJsonBlob() const { return true; }

    XJsonBlobSink(MdsdConfig* config, const MdsEntityName &target, const Credentials* c);

    virtual ~XJsonBlobSink();

    virtual void AddRow(const CanonicalEntity&, const MdsTime&);

    virtual void Flush();

    virtual void ValidateAccess();

private:
    XJsonBlobSink();

    // This code path is currently really not used (as we haven't actually
    // implemented the OboDirect feature), but just placed for the future.
    void InitializeForOboDirect(MdsdConfig* config, const std::shared_ptr<mdsd::OboDirectConfig>& oboDirectConfig);

    // This will be mostly used for LAD JsonBlob sink scenario.
    void InitializeForLadWithoutOboDirect(MdsdConfig* config);

    void ComputeConnString();

    RequestInfo _template;

    const Credentials* _creds;

    std::string _namespace;

    std::string _containerName;

    std::shared_ptr<XJsonBlobRequest> _request;

    // Per-blob block list that needs to be persisted across multiple requests,
    // so keep it here as a shared ptr. XJBS just maintains a pointer (so that
    // it can be persisted across multiple requests) and all operations on it
    // are done by XJBR.
    std::shared_ptr<BlockListT> _blockList;

    // Block list reconstruction from a persisted block count file is needed
    // only for the first request, so remember whether first request was created or not.
    bool _firstReqCreated;

    MdsTime _blobBaseTime;  // Base time for which we're currently building a blob.

    time_t _blobIntervalSec;        // E.g., 1 hour (3600 sec). Fixed interval in seconds for a blob.
    std::string _blobIntervalISO8601Duration;   // E.g., "PT1H". _blobIntervalSec should be computed from this. If this is not a correct ISO8601 string, it should be "PT1H" by default.

    // Maintained by ComputeConnString()
    std::string _connString;

    // Other constants
    static constexpr size_t _targetBlockSize { 4128768 };	// 4MB - 64KB
};

#endif // _XJSONBLOBSINK_HH_

// vim: se sw=4 :
