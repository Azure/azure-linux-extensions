// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __GCSUTIL_HH__
#define __GCSUTIL_HH__

#include <string>
#include <cpprest/json.h>

#include "MdsRestException.hh"

namespace mdsd
{

namespace GcsUtil
{
    // <summary>
    // Get a string format of a JSON value type.
    // </summary>
    std::string GetJsonTypeStr(web::json::value::value_type t);

    // <summary>
    // Throw JsonParseException if actual type is not equal to expected type
    // for an item with name called itemName.
    // </summary>
    void ThrowIfInvalidType(const std::string & itemName,
        web::json::value::value_type expectedType, web::json::value::value_type actualType);

    // <summary>
    // Get GCS service endpoint given GCS environment value (e.g. "Test")
    // This function is used when GCS environment is defined but GCS endpoint
    // is empty. This can avoid customer to remember the exact endpoint.
    // Customer can still define endpoint if needed.
    // </summary>
    std::string GetGcsEndpointFromEnvironment(const std::string & gcsEnvName);

} // namespace GcsUtil

} // namespace mdsd

#endif // __GCSUTIL_HH__
