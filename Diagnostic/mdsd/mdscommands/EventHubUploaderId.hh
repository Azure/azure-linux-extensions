// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _EVENTHUBUPLOADERID_HH_
#define _EVENTHUBUPLOADERID_HH_

#include <string>
#include "EventHubType.hh"

namespace mdsd {

struct EventHubUploaderId {
    EventHubType m_ehtype;
    std::string m_moniker;
    std::string m_eventname;

    EventHubUploaderId(EventHubType ehtype, const std::string & moniker, const std::string & eventname);
    EventHubUploaderId(const std::string & idstr);

    operator std::string() const {
        // put the bits that change more frequently at the front
        return (m_eventname + " " + m_moniker + " " + EventHubTypeToStr(m_ehtype));
    }
};

} // namespace mdsd

inline std::ostream&
operator<<(
    std::ostream& os,
    const mdsd::EventHubUploaderId& id
    )
{
    os << static_cast<std::string>(id);
    return os;
}

#endif // _EVENTHUBUPLOADERID_HH_
