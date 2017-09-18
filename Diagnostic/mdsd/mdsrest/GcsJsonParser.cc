// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <sstream>

#include "GcsJsonParser.hh"
#include "GcsUtil.hh"
#include "Logger.hh"
#include "Trace.hh"
#include "GcsJsonData.hh"

using namespace mdsd;
using namespace mdsd::details;


bool
GcsJsonParser::Parse(
    GcsAccount & gcsAccount
    )
{
    Trace trace(Trace::MdsCmd, "GcsJsonParser::Parse");
    if (!m_jsonStr.empty()) {
        try {
            m_jsonObj = web::json::value::parse(m_jsonStr);
        }
        catch(const std::exception & ex) {
            Logger::LogError("Error: failed to parse JSON string '" + m_jsonStr + "': " + ex.what());
            return false;
        }
    }
    if (!m_jsonObj.is_null()) {
        try {
            JsonObjectParser<GcsAccount> rootParser("", m_jsonObj);
            rootParser.Parse(gcsAccount);
            if (trace.IsActive()) {
                std::ostringstream ostr;
                ostr << gcsAccount;
                TRACEINFO(trace, ostr.str());
            }
        }
        catch(const std::exception & ex) {
            Logger::LogError(std::string("Error: failed to parse JSON object: ") + ex.what());
            return false;
        }
    }
    return true;
}

void
GcsJsonBaseParser::CheckType() const
{
    GcsUtil::ThrowIfInvalidType(GetPath(), GetExpectedType(), GetActualType());
}

void
GcsJsonBaseParser::LogMsgIfUnrecognized(
    const std::string & itemname
    ) const
{
    std::ostringstream msg;
    msg << "Ignore unrecognized item: '" << itemname << "'";
    // Because future GCS may add additional JSON key/value pairs, only log unrecognized
    // name as information only.
    Logger::LogInfo(msg.str());
}

void
EventHubKeysParser::Parse(
    std::unordered_map<std::string, EventHubKey>& ehkeymap
    )
{
    CheckType();
    auto & jsonObj = GetJson().as_object();

    for (auto iter = jsonObj.cbegin(); iter != jsonObj.cend(); ++iter) {
        const auto & name = iter->first;
        const auto & value = iter->second;

        if (ehkeymap.find(name) != ehkeymap.end()) {
            throw JsonParseException("Found duplicate item: " + GetPath() + "/" + name);
        }

        EventHubKey ehkey;
        JsonObjectParser<EventHubKey> ehkeyParser(GetPath() + "/" + name, value);
        ehkeyParser.Parse(ehkey);

        ehkeymap[name] = std::move(ehkey);
    }
}

void
StringArrayParser::Parse(
    std::vector<std::string>& resultList
    )
{
    CheckType();
    auto & array = GetJson().as_array();

    for (size_t i = 0; i < array.size(); i++) {
        auto jsontype = array.at(i).type();

        if (web::json::value::String == jsontype) {
            resultList.push_back(array.at(i).as_string());
        }
        else {
            throw JsonParseException("StringArrayParser: unsupported JSON type '" +
                GcsUtil::GetJsonTypeStr(jsontype) + "'");
        }
    }
}
