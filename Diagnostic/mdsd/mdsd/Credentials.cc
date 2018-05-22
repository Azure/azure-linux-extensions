// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "Credentials.hh"
#include <sstream>
#include <cstdlib>
#include "Trace.hh"
#include "Logger.hh"
#include "MdsdConfig.hh"
#include "Utility.hh"
#include "AzureUtility.hh"

using std::string;

std::ostream&
operator<<(std::ostream &os, const Credentials& creds)
{
    os << &creds << "=(Moniker " << creds.Moniker() << " type " << creds.TypeName() << ")";
    return os;
}

const std::string&
Credentials::ServiceType_to_string(ServiceType svcType)
{
    static std::map<Credentials::ServiceType, std::string> stmap =
    {
        { Credentials::ServiceType::XTable, "XTable" },
        { Credentials::ServiceType::Blob, "Blob" },
        { Credentials::ServiceType::EventPublish, "EventPublish" }
    };
    static std::string UnknownType { "Unknown ServiceType" };
    auto iter = stmap.find(svcType);
    if (iter == stmap.end()) {
        return UnknownType;
    } else {
        return iter->second;
    }
}

std::ostream&
operator<<(std::ostream &os, Credentials::ServiceType svcType)
{
    os << Credentials::ServiceType_to_string(svcType);
    return os;
}


// Extract the "se" part of the query string and expire 30-60 minutes before then
MdsTime
CredentialType::AutoKey::GetExpireTimeFromSasSE(const std::string & sas)
{
    std::map<string, string> qry;
    MdsdUtil::ParseQueryString(sas, qry);
    auto exp = qry.find("se");
    if (exp == qry.end()) {
        // Shouldn't happen, but if it does, the URI should be good for 11-12 hours.
        return (MdsTime::Now() + MdsTime(11 * 3600 + random()%3600));
    } else {
        return (MdsTime(exp->second) - MdsTime(1800 + random()%1800));
    }
}

// Three output parameters are set by the ConnectionString() methods
//
// For XTable, fullSvcName will be set to the actual XStore table name to be used. The namespace prefix and the version
//      and perNDay suffixes will be applied as appropriate. The perNDay selected is "right now".
// connstr will be set to the connection string.
// expires will be set to the expiration time of the connection string (i.e. the time at which a new
//      connection string should be requested).
//
// Returns true if a connection string could be constructed; false if not.


bool
CredentialType::Local::ConnectionString(const MdsEntityName &target, ServiceType svcType,
        string &fullSvcName, string &connstr, MdsTime &expires) const
{
    Trace trace(Trace::Credentials, "ConnectionString Local");
    Logger::LogError("Can't make connection string for Local moniker " + Moniker());
    return false;
}

bool
CredentialType::SharedKey::ConnectionString(const MdsEntityName &target, ServiceType svcType,
        string &fullSvcName, string &connstr, MdsTime &expires) const
{
    Trace trace(Trace::Credentials, "ConnectionString SharedKey");

    try {
        connstr = GetConnectionStringOnly(svcType);
    } catch (std::invalid_argument& e) {
        trace.NOTE(e.what());
        Logger::LogError(e.what());
        return false;
    }

    fullSvcName = target.Name();

    if (target.IsConstant()) {
        expires = MdsTime::Max();
    } else {
        // Rebuild connection string at next ten-day interval
        expires = (MdsTime::Now() + 10*24*3600).RoundTenDay();
    }

    return true;
}


std::string
CredentialType::SharedKey::GetConnectionStringOnly(ServiceType svcType) const
{
    std::ostringstream conn;

    if (ServiceType::Blob == svcType) {
        conn << "BlobEndpoint=" << _blobUri;
    }
    else if (ServiceType::XTable == svcType) {
        conn << "TableEndpoint=" << _tableUri;
    }
    else {
        throw invalid_type(svcType);
    }

    conn << ";AccountName=" << _accountName << ";AccountKey=" << _secret;

    return conn.str();
}


bool
CredentialType::AutoKey::ConnectionString(
        const MdsEntityName &target,
        ServiceType svcType,
        string &fullSvcName,
        string &connstr,
        MdsTime &expires) const
{
    Trace trace(Trace::Credentials, "ConnectionString AutoKey");

    std::ostringstream conn;

    string autokey;

    switch (svcType) {
    case ServiceType::EventPublish:
        fullSvcName = target.EventName();
        autokey = _config->GetEventPublishCmdXmlItems(Moniker(), fullSvcName).sas;
        break;
    case ServiceType::Blob:
    case ServiceType::XTable:
        fullSvcName = target.Name();
        autokey = _config->GetAutokey(Moniker(), fullSvcName);
        break;
    default:
        std::ostringstream strm;
        strm << "Error: AutoKey credential doesn't support service " << svcType;
        trace.NOTE(strm.str());
        Logger::LogError(strm.str());
        return false;
    }

    if (autokey.empty()) {
        std::ostringstream strm;
        strm << "Can't find autokey for moniker " << Moniker() << ", " << svcType << " " << fullSvcName;
        trace.NOTE(strm.str());
        Logger::LogError(strm.str());
        return false;
    }

    string endpointName;
    string endpointSep;
    if (ServiceType::XTable == svcType) {
        endpointName = "TableEndpoint";
        endpointSep = "/$batch?";
    }
    else if (ServiceType::Blob == svcType) {
        endpointName = "BlobEndpoint";
        endpointSep = "/" + fullSvcName + "?";
    }

    size_t pos = autokey.find(endpointSep);	// Separates endpoint from SAS
    if (pos == string::npos) {
        std::ostringstream msg;
        msg << "Improperly formatted autokey for " << Moniker() << ", " << svcType << " " << fullSvcName;
        msg << ": \"" << autokey << "\"";
        trace.NOTE(msg.str());
        Logger::LogError(msg.str());
        return false;
    }
    conn << endpointName << "=" << autokey.substr(0, pos);
    conn << ";SharedAccessSignature=" << autokey.substr(pos+endpointSep.size());

    if (!autokey.empty()) {
        expires = GetExpireTimeFromSasSE(autokey);
    }

    // If the tablename can change, rebuild at the change time, if that's sooner
    if (!target.IsConstant()) {
        MdsTime proposed = (MdsTime::Now() + 10*24*3600).RoundTenDay();
        if (proposed < expires) {
            expires = proposed;
        }
    }

    connstr = conn.str();
    trace.NOTE("AutoKey ConnectionString='" + connstr + "'.");
    return true;
}

mdsd::EhCmdXmlItems
CredentialType::AutoKey::GetEhParameters(const std::string& eventName,
	Credentials::ServiceType eventType
	) const
{
    if (Credentials::ServiceType::EventPublish == eventType) {
        return _config->GetEventPublishCmdXmlItems(Moniker(), eventName);
    }
    throw invalid_type(eventType);
}

CredentialType::SAS::SAS(const std::string& moniker, const std::string& acct, const std::string &token)
	: Credentials(moniker, SecretType::SAS), _secret(token), _accountName(acct),
	  _blobUri(MakePublicCloudEndpoint(acct, ServiceType::Blob)),
	  _tableUri(MakePublicCloudEndpoint(acct, ServiceType::XTable))
{
    MdsdUtil::ValidateSAS(token, _isAccountSas);
}

std::string
CredentialType::SAS::GetConnectionStringOnly(ServiceType svcType) const
{
    std::ostringstream conn;

    if (ServiceType::XTable == svcType) {
        conn << "TableEndpoint=" << _tableUri;
    }
    else if (ServiceType::Blob == svcType) {
        conn << "BlobEndpoint=" << _blobUri;
    }
    else {
        throw invalid_type(svcType);
    }
    conn << ";SharedAccessSignature=" << _secret;

    return conn.str();
}

bool
CredentialType::SAS::ConnectionString(const MdsEntityName &target, ServiceType svcType,
	string &fullSvcName, string &connstr, MdsTime &expires) const
{
    Trace trace(Trace::Credentials, "ConnectionString SAS");

    try {
        connstr = GetConnectionStringOnly(svcType);
    } catch (std::invalid_argument& e) {
        trace.NOTE(e.what());
        Logger::LogError(e.what());
        return false;
    }

    std::map<string, string> qry;
    MdsdUtil::ParseQueryString(_secret, qry);

    if (IsAccountSas()) {
        // The SAS is an account SAS, replacing the storage shared key, and the svc name should be a name with
        // the 10-day suffix, not the base name.
        fullSvcName = target.Name();
    }
    else if (ServiceType::XTable == svcType) {
        // SAS (non-account SAS) includes the tablename; update to match, otherwise the SAS won't work.
        auto item = qry.find("tn");
        if (item != qry.end()) {
            fullSvcName = item->second;
        } else {
            Logger::LogError("SAS for MDS moniker " + Moniker() + " missing tn= component");
            fullSvcName = target.Basename();
        }
    }

    auto exp = qry.find("se");
    if (exp == qry.end()) {
        expires = MdsTime::Max();	// No expiration in SAS
    } else {
        expires = MdsTime(exp->second);
        if (MdsTime::Now() > expires) {
            Logger::LogError("Expired SAS for MDS moniker " + Moniker());
        }
    }

    if (IsAccountSas()) {
        // Set expires for next ten-day interval, following the storage shared key credential logic.
        // (Note: The account SAS itself will/should never expire, like a storage shared key)
        expires = std::min(expires, (MdsTime::Now() + 10*24*3600).RoundTenDay());
    }

    return true;
}

// vim: se sw=4 expandtab :
