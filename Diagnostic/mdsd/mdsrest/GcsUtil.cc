// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <map>
#include <unordered_map>
#include <sstream>

#include "GcsUtil.hh"

namespace mdsd { namespace GcsUtil {

static std::map<web::json::value::value_type, std::string>&
GetJsonTypeMap()
{
    static std::map<web::json::value::value_type, std::string> m =
    {
        { web::json::value::Number, "Number" },
        { web::json::value::Boolean, "Boolean" },
        { web::json::value::String, "String" },
        { web::json::value::Object, "Object" },
        { web::json::value::Array, "Array" },
        { web::json::value::Null, "Null" }
    };
    return m;
}

std::string
GetJsonTypeStr(web::json::value::value_type t)
{
    auto & m = GetJsonTypeMap();
    auto item = m.find(t);
    if (item != m.end()) {
        return item->second;
    }
    return "Unknown";
}

void
ThrowIfInvalidType(
    const std::string & itemName,
    web::json::value::value_type expectedType,
    web::json::value::value_type actualType
    )
{
    if (expectedType != actualType) {
        std::ostringstream ostr;
        ostr << "Json item '" << itemName << "' has invalid type:"
             << " expected=" << GetJsonTypeStr(expectedType)
             << " actual=" << GetJsonTypeStr(actualType);
        throw JsonParseException(ostr.str());
    }
}

// key: Gcs Environment. e.g. "Test"
// value: Gcs endpoing. e.g. "ppe.warmpath.msftcloudes.com"
static std::unordered_map<std::string, std::string>&
GetGcsEnvEndPointMap()
{
    static std::unordered_map<std::string, std::string> m = {
        {"DiagnosticsProd", "prod.warmpath.msftcloudes.com"},
        {"FirstPartyProd",  "prod.warmpath.msftcloudes.com"},
        {"Test",            "ppe.warmpath.msftcloudes.com"},
        {"Stage",           "ppe.warmpath.msftcloudes.com"},
        {"BillingProd",     "prod.warmpath.msftcloudes.com"},
        {"ExternalProd",    "prod.warmpath.msftcloudes.com"},
        {"CaMooncake",      "mooncake.warmpath.chinacloudapi.cn"},
        {"CaBlackforest",   "blackforest.warmpath.cloudapi.de"},
        {"CaFairfax",       "fairfax.warmpath.usgovcloudapi.net"}
    };
    return m;
}

std::string
GetGcsEndpointFromEnvironment(
    const std::string & gcsEnvName
    )
{
    auto & m = GetGcsEnvEndPointMap();
    auto item = m.find(gcsEnvName);
    if (item == m.end()) {
        return std::string();
    }
    return item->second;
}

} // namespace GcsUtil
} // namespace mdsd
