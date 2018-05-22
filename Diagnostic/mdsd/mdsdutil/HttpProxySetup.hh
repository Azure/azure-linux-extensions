// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _HTTPPROXYSETUP_HH_
#define _HTTPPROXYSETUP_HH_

#include <string>
#include <stdexcept>
#include <vector>

namespace MdsdUtil {


class HttpProxySetupException : public std::runtime_error
{
public:
    HttpProxySetupException(const std::string& message)
        : std::runtime_error(message)
    {}
};

/// <summary>
/// Sets up Storage C++ SDK's http proxy by calling corresponding Azure Storage C++ API.
/// Throws an HttpProxySetupException if it fails.
/// proxy_config_string format is "[[http[s]:]//][username[:password]@]host[:port]".
/// </summary>
void SetStorageDefaultHttpProxy(const std::string& proxy_config_string);

/// <summary>
/// Checks if the proxy_setting_string is valid. Throws an HttpProxySetupException
/// if it's invalid. Noop otherwise.
/// proxy_config_string format is "[[http[s]:]//][username[:password]@]host[:port]".
/// </summary>
void CheckProxySettingString(const std::string& proxy_setting_string);

/// <summary>
/// Get the address of the proxy server for Storage SDK's default (global) http/https proxy.
/// Address is of form "//host[:port]".
/// </summary>
std::string GetStorageDefaultHttpProxyAddress();

/// <summary>
/// Set Azure Storage API http proxy to one of the following values, with
/// first one tried first if it is not empty:
/// - proxySetting
/// - ordered list of environment variables in proxyEnvVars.
/// Throw exception for any error.
void SetStorageHttpProxy(std::string proxySetting, const std::vector<std::string> & proxyEnvVars);

/// <summary>
/// Remove Azure Storage API http proxy.
/// </summary>
void RemoveStorageHttpProxy();

} // namespace MdsdUtil

#endif // _HTTPPROXYSETUP_HH_
