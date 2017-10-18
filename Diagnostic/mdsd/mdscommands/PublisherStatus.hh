// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __PUBLISHERSTATUS_HH__
#define __PUBLISHERSTATUS_HH__

#include <iosfwd>

namespace mdsd { namespace details
{

enum class PublisherStatus
{
    /// <summary>
    /// Object has not started any work.
    /// </summary>
    Idle,

    /// <summary>
    /// The last publication attempt succeeded.
    /// </summary>
    PublicationSucceeded,

    /// <summary>
    /// The last publication attempt failed.
    /// </summary>
    PublicationFailedWithUnknownReason,

    /// <summary>
    /// The last publication attempt failed with bad request error.
    /// </summary>
    PublicationFailedWithBadRequest,

    /// <summary>
    /// The last publication attempt failed with auth error.
    /// </summary>
    PublicationFailedWithAuthError,

    /// <summary>
    /// The last publication attempt failed because server is busy, need to retry later.
    /// </summary>
    PublicationFailedServerBusy,

    /// <summary>
    /// The last publication attempt failed because of throttled, need to retry later.
    /// </summary>
    PublicationFailedThrottled
};

} // namespace details
} // namespace mdsd

std::ostream&
operator<<(
    std::ostream& os,
    mdsd::details::PublisherStatus status
    );


#endif // __PUBLISHERSTATUS_HH__
