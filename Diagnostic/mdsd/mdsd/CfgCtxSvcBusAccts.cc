// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "CfgCtxSvcBusAccts.hh"
#include "MdsdConfig.hh"
#include "EventPubCfg.hh"
#include "Trace.hh"
#include "Utility.hh"
#include "cryptutil.hh"

///////// CfgCtxSvcBusAccts

subelementmap_t CfgCtxSvcBusAccts::_subelements = {
    { "ServiceBusAccountInfo", [](CfgContext* parent) -> CfgContext* { return new CfgCtxSvcBusAcct(parent); } }
};

std::string CfgCtxSvcBusAccts::_name = "ServiceBusAccountInfos";

///////// CfgCtxSvcBusAcct

subelementmap_t CfgCtxSvcBusAcct::_subelements = {
    { "EventPublisher", [](CfgContext* parent) -> CfgContext* { return new CfgCtxEventPublisher(parent); } }
};

std::string CfgCtxSvcBusAcct::_name = "ServiceBusAccountInfo";

void
CfgCtxSvcBusAcct::Enter(const xmlattr_t& properties)
{
    Trace trace(Trace::ConfigLoad, "CfgCtxSvcBusAcct::Enter");
    const std::string & attrMoniker = "name";

    for (const auto& item : properties)
    {
        if (attrMoniker == item.first) {
            parse_singleton_attribute(item.first, item.second, attrMoniker, _moniker);
        }
        else {
            warn_if_attribute_unexpected(item.first);
        }
    }

    fatal_if_no_attributes(attrMoniker, _moniker);
}

///////// CfgCtxEventPublisher

subelementmap_t CfgCtxEventPublisher::_subelements;
std::string CfgCtxEventPublisher::_name = "EventPublisher";

void
CfgCtxEventPublisher::Enter(const xmlattr_t& properties)
{
    std::string valConnStr;
    std::string valDecryptKeyPath;

    const std::string & attrConnStr = "connectionString";
    const std::string & attrDecryptKeyPath = "decryptKeyPath";

    for (const auto & item : properties)
    {
        if (attrConnStr == item.first) {
            parse_singleton_attribute(item.first, item.second, attrConnStr, valConnStr);
        }
        else if (attrDecryptKeyPath == item.first) {
            parse_singleton_attribute(item.first, item.second, attrDecryptKeyPath, valDecryptKeyPath);
        }
        else {
            warn_if_attribute_unexpected(item.first);
        }
    }
    fatal_if_no_attributes(attrConnStr, valConnStr);

    auto sbObj = dynamic_cast<CfgCtxSvcBusAcct*>(ParentContext);
    if (!sbObj) {
        fatal_if_impossible_subelement();
        return;
    }
    auto sbmoniker = sbObj->GetMoniker();
    try {
        if (valDecryptKeyPath.empty()) {
            auto escapedConnStr = MdsdUtil::UnquoteXmlAttribute(valConnStr);
            Config->GetEventPubCfg()->AddServiceBusAccount(sbmoniker, std::move(escapedConnStr));
        }
        else {
            if (!MdsdUtil::IsRegFileExists(valDecryptKeyPath)) {
                ERROR("Cannot find decrypt key path " + valDecryptKeyPath);
            }
            else {
                auto decryptedSas = cryptutil::DecodeAndDecryptString(valDecryptKeyPath, std::move(valConnStr));
                Config->GetEventPubCfg()->AddServiceBusAccount(sbmoniker, std::move(decryptedSas));
            }
        }
    }
    catch(const std::exception & ex) {
        ERROR("<" + Name() + "> exception: " + ex.what());
    }
}
