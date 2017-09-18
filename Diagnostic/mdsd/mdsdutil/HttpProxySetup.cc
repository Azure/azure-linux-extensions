// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <cpprest/uri.h>
#include <was/common.h>
#include <boost/regex.hpp>

#include "HttpProxySetup.hh"
#include "Utility.hh"
#include "Logger.hh"

namespace MdsdUtil {

static web::web_proxy GetProxySetting(
    const std::string& proxy_setting_string // "[[http[s]:]//][username[:password]@]host[:port]"
)
{
    std::string host_port;          // "//host[:port]" for CPPREST API
    std::string username, password; // Should be URL-decoded

     boost::regex re { R"(^\s*((https?:)?//)?((([^:/@\s]+)(:([^:/@\s]+))?)@)?([\w.\-]+)(:([0-9]+))?\s*$)" };
    // Submatch 0 is the whole string
    // Submatch 5 is the optional (but required if @ is present) username
    // Submatch 7 is the optional password
    // Submatch 8 is the required hostname
    // Submatch 10 is the optional port number
    boost::smatch matches;
    if (!boost::regex_match(proxy_setting_string, matches, re)) {
        // No match
        throw HttpProxySetupException("Invalid proxy setting string");
    }
    
    // We've got a match
#define FIELD_TO_STRING(FN) (std::string(matches[FN].first, matches[FN].second))
    try {
        if (matches[5].matched) {
            username = web::uri::decode(FIELD_TO_STRING(5));
        }
        if (matches[7].matched) {
            password = web::uri::decode(FIELD_TO_STRING(7));
        }
    } catch (web::uri_exception& e) {
        throw HttpProxySetupException(std::string("Exception occurred when URL-decoding username "
                                                  " or password. Exception message: ")
                                     + e.what());
    }

    if (matches[8].matched) {
        host_port = std::string("//") + FIELD_TO_STRING(8);
    }
    if (matches[10].matched) {
        host_port += std::string(":") + FIELD_TO_STRING(10);
    }

    web::web_proxy proxy_setting(_XPLATSTR(host_port.c_str()));
    if (!username.empty()) {
        proxy_setting.set_credentials(web::credentials(_XPLATSTR(username.c_str()), _XPLATSTR(password.c_str())));
    }

    return proxy_setting;
}

void SetStorageDefaultHttpProxy(const std::string& proxy_setting_string)
{
    web::web_proxy proxy_setting = GetProxySetting(proxy_setting_string);

    azure::storage::operation_context::set_default_proxy(proxy_setting);

    std::ostringstream msg;
    msg << "Set http proxy for Azure Storage API with '" << proxy_setting_string << "'. ";
    msg << "The resulted http proxy setting is '" << MdsdUtil::GetStorageDefaultHttpProxyAddress() << "'.";
    Logger::LogInfo(msg);
}

void CheckProxySettingString(const std::string& proxy_setting_string)
{
    GetProxySetting(proxy_setting_string);
}

std::string GetStorageDefaultHttpProxyAddress()
{
    web::web_proxy default_proxy = azure::storage::operation_context::default_proxy();

    return default_proxy.address().to_string();
}

void
SetStorageHttpProxy(
    std::string proxy_setting_string,
    const std::vector<std::string> & proxyEnvVars
    )
{
    std::string proxy_env_var_name;

    if (proxy_setting_string.empty()) {
        for (auto env : proxyEnvVars) {
            proxy_setting_string = MdsdUtil::GetEnvironmentVariableOrEmpty(env);
            if (!proxy_setting_string.empty()) {
                proxy_env_var_name = env;
                break;
            }
        }
    }

    if (!proxy_setting_string.empty()) {
        try {
            SetStorageDefaultHttpProxy(proxy_setting_string);
        }
        catch(const HttpProxySetupException& ex) {
            std::ostringstream msg;
            msg << "Fatal error: setting http proxy for Azure Storage API to '" << proxy_setting_string << "' ";
            if (!proxy_env_var_name.empty()) {
                msg << "from environment variable '" << proxy_env_var_name << "' ";
            }
            msg << "failed: " << ex.what();
            throw std::runtime_error(msg.str());
        }
    }
}

void
RemoveStorageHttpProxy()
{
    web::web_proxy proxy_setting;
    azure::storage::operation_context::set_default_proxy(proxy_setting);
}

} // namespace MdsdUtil
