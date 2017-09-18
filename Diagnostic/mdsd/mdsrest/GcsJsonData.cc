// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "GcsJsonData.hh"
#include "GcsUtil.hh"
#include "Logger.hh"
#include "MdsConst.hh"

using namespace mdsd;

static std::string
GetStringFromJson(
    const std::string & itemname,
    const web::json::value& jsonObj
    )
{
    GcsUtil::ThrowIfInvalidType(itemname, web::json::value::String, jsonObj.type());
    return jsonObj.as_string();
}

std::ostream&
mdsd::operator<<(std::ostream & os, const EventHubKey& obj)
{
    os << "    SasKey='" << obj.SasKey << "'; Uri='" << obj.Uri << "'.\n";
    return os;
}

std::unordered_map<std::string, itemparser_t<EventHubKey>> EventHubKey::ParserMap = {
    { "SasKey", [](const std::string & name, const web::json::value & value, EventHubKey& result)
        {
            result.SasKey = GetStringFromJson(name, value);
        }
    },
    { "Uri", [](const std::string & name, const web::json::value & value, EventHubKey& result)
        {
            result.Uri = GetStringFromJson(name, value);
        }
    }
};


std::ostream&
mdsd::operator<<(std::ostream & os, const ServiceBusAccountKey& obj)
{
    os << "AccountGroupName='" << obj.AccountGroupName << "'; AccountMonikerName='" << obj.AccountMonikerName << "'.\n";
    for (const auto & item : obj.EventHubKeys) {
        os << "EventHubsKeys: " << item.first << ":" << item.second;
    }
    return os;
}

// Instead of return when an invalid item is found, the validation will do
// as much validation as possible.
bool
ServiceBusAccountKey::IsValid() const
{
    bool retVal = true;

    if (AccountGroupName.empty() || AccountMonikerName.empty() || EventHubKeys.empty()) {
        Logger::LogError("Error: ServiceBusAccountKey has invalid empty field");
        retVal = false;
    }

    for (const auto & item : EventHubKeys) {
        if (!item.second.IsValid()) {
            Logger::LogError("Error: EventHubKey '" + item.first + "' is invalid");
            retVal = false;
        }
    }

    return retVal;
}

std::unordered_map<std::string, itemparser_t<ServiceBusAccountKey>> ServiceBusAccountKey::ParserMap = {
    { "AccountGroupName", [](const std::string & name, const web::json::value & value, ServiceBusAccountKey& result)
      {
          result.AccountGroupName = GetStringFromJson(name, value);
      }
    },
    { "AccountMonikerName", [](const std::string & name, const web::json::value & value, ServiceBusAccountKey& result)
      {
          result.AccountMonikerName = GetStringFromJson(name, value);
      }
    },
    { "EventHubKeys", [](const std::string & name, const web::json::value & value, ServiceBusAccountKey& result)
      {
          details::EventHubKeysParser ehkeysParser(name, value);
          ehkeysParser.Parse(result.EventHubKeys);
      }
    }
};


std::unordered_map<std::string, itemparser_t<StorageSasKey>> StorageSasKey::ParserMap = {
    { "ResourceName", [](const std::string & name, const web::json::value & value, StorageSasKey& result)
        {
            result.ResourceName = GetStringFromJson(name, value);
        }
    },
    { "SasKey", [](const std::string & name, const web::json::value & value, StorageSasKey& result)
        {
            result.SasKey = GetStringFromJson(name, value);
        }
    },
    { "SasKeyType", [](const std::string & name, const web::json::value & value, StorageSasKey& result)
        {
            result.SasKeyType = GetStringFromJson(name, value);
        }
    }
};


std::ostream&
mdsd::operator<<(std::ostream & os, const StorageSasKey& obj)
{
    os << "ResourceName='" << obj.ResourceName << "'; SasKey='" << obj.SasKey
       << "'; SasKeyType='" << obj.SasKeyType << "'\n";
    return os;
}

std::ostream&
mdsd::operator<<(std::ostream & os, const StorageAccountKey& obj)
{
    os  << "StorageAccountName='" << obj.StorageAccountName << "'; "
        << "AccountGroupName='" << obj.AccountGroupName << "'; "
        << "AccountMonikerName='" << obj.AccountMonikerName << "'; "
        << "BlobEndpoint='" << obj.BlobEndpoint << "'; "
        << "QueueEndpoint='" << obj.QueueEndpoint << "'; "
        << "TableEndpoint='" << obj.TableEndpoint << "'.\n";

    for (const auto & item : obj.SasKeys) {
        os << item;
    }
    return os;
}

// Return true if equal, false if not equal.
// Log error if not equal.
static inline bool
ValidateEqual(
    int expected,
    int actual,
    const std::string & msg
    )
{
    if (expected != actual) {
        std::ostringstream ostr;
        ostr << "Error: " << msg << ": expected=" << expected << "; actual=" << actual;
        Logger::LogError(ostr);
        return false;
    }
    return true;
}

bool
StorageAccountKey::IsValid() const
{
    bool retVal = true;

    if (StorageAccountName.empty() ||
        AccountGroupName.empty() ||
        AccountMonikerName.empty() ||
        BlobEndpoint.empty() ||
        QueueEndpoint.empty() ||
        TableEndpoint.empty() ||
        SasKeys.empty()) {
        Logger::LogError("Error: StorageAccountKey has invalid empty field");
        retVal = false;
    }

    // The Blob and Table SAS keys must be defined exactly once
    int nBlobSas = 0;
    int nTableSas = 0;
    const int nexpected = 1;

    for (const auto & item : SasKeys) {
        if (!item.IsValid()) {
            retVal = false;
        }
        if ("BlobService" == item.SasKeyType) {
            nBlobSas++;
        }
        else if ("TableService" == item.SasKeyType) {
            nTableSas++;
        }
    }

    retVal &= ValidateEqual(nexpected, nBlobSas, "# of BlobService SasKeys");
    retVal &= ValidateEqual(nexpected, nTableSas, "# of TableService SasKeys");

    return retVal;
}

std::unordered_map<std::string, itemparser_t<StorageAccountKey>> StorageAccountKey::ParserMap = {
    { "StorageAccountName", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            result.StorageAccountName = GetStringFromJson(name, value);
        }
    },
    { "AccountGroupName", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            result.AccountGroupName = GetStringFromJson(name, value);
        }
    }
    ,
    { "AccountMonikerName", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            result.AccountMonikerName = GetStringFromJson(name, value);
        }
    }
    ,
    { "BlobEndpoint", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            result.BlobEndpoint = GetStringFromJson(name, value);
        }
    }
    ,
    { "QueueEndpoint", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            result.QueueEndpoint = GetStringFromJson(name, value);
        }
    }
    ,
    { "TableEndpoint", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            result.TableEndpoint = GetStringFromJson(name, value);
        }
    },
    { "SasKeys", [](const std::string & name, const web::json::value & value, StorageAccountKey& result)
        {
            details::ObjectArrayParser<StorageSasKey> arrayParser(name, value);
            arrayParser.Parse(result.SasKeys);
        }
    }
};


std::ostream&
mdsd::operator<<(std::ostream & os, const GcsAccount& obj)
{
    os << "\nMaSigningPublicKeys: " << obj.MaSigningPublicKeys.size() << "\n";
    for (const auto & item : obj.MaSigningPublicKeys) {
        os << item;
    }

    os << "SasKeysExpireTimeUtc='" << obj.SasKeysExpireTimeUtc << "';\n";

    for (const auto & item: obj.ServiceBusAccountKeys) {
        os << item;
    }

    for (const auto & item: obj.StorageAccountKeys) {
        os << item;
    }

    os << "TagId='" << obj.TagId << "'.";
    return os;
}

static bool
ValidateMaSigningPublicKeys(
    const std::vector<std::string> & MaSigningPublicKeys
    )
{
    bool retVal = true;
    if (MaSigningPublicKeys.empty()) {
        Logger::LogError("Error: unexpected empty MaSigningPublicKey array");
        retVal = false;
    }

    for (const auto & item: MaSigningPublicKeys) {
        if (item.empty()) {
            Logger::LogError("Error: unexpected invalid MaSigningPublicKey");
            retVal = false;
        }
    }
    return retVal;
}

static bool
ValidateServiceBusAccountKeys(
    const std::vector<ServiceBusAccountKey> & ServiceBusAccountKeys
    )
{
    bool retVal = true;

    if (ServiceBusAccountKeys.empty()) {
        Logger::LogError("Error: unexpected empty ServiceBusAccountKeys array");
        retVal = false;
    }

    size_t i = 0;
    for (const auto & item : ServiceBusAccountKeys) {
        if (!item.IsValid()) {
            Logger::LogError("Error: ServiceBusAccountKeys[" + std::to_string(i) + "] is invalid");
            retVal = false;
        }
        i++;
    }

    // Validate that required EventHub keys exist
    if (!ServiceBusAccountKeys.empty()) {
        int nEHNoticeKeys = 0;
        int nEHPublishKeys = 0;
        const int nexpected = 1;

        for (auto & item : ServiceBusAccountKeys) {
            if (item.EventHubKeys.count(gcs::c_EventHub_notice)) {
                nEHNoticeKeys++;
            }
            if (item.EventHubKeys.count(gcs::c_EventHub_publish)) {
                nEHPublishKeys++;
            }
        }

        retVal &= ValidateEqual(nexpected, nEHNoticeKeys, "# EventHubKey for '" + gcs::c_EventHub_notice + "'");
        retVal &= ValidateEqual(nexpected, nEHPublishKeys, "# EventHubKey for '" + gcs::c_EventHub_publish + "'");
    }

    return retVal;
}

static bool
ValidateStorageAccountKeys(
    const std::vector<StorageAccountKey> & StorageAccountKeys
    )
{
    bool retVal = true;

    if (StorageAccountKeys.empty()) {
        Logger::LogError("Error: unexpected empty StorageAccountKeys array");
        retVal = false;
    }

    size_t i = 0;
    for (const auto & item : StorageAccountKeys) {
        if (!item.IsValid()) {
            Logger::LogError("Error: StorageAccountKeys[" + std::to_string(i) + "] is invalid");
            retVal = false;
        }
        i++;
    }
    return retVal;
}

bool
GcsAccount::IsValid() const
{
    bool retVal = true;

    if (TagId.empty()) {
        retVal = false;
    }

    if (IsEmpty()) {
        return retVal;
    }

    retVal &= ValidateMaSigningPublicKeys(MaSigningPublicKeys);

    if (SasKeysExpireTimeUtc.empty()) {
        Logger::LogError("Error: unexpected empty SasKeysExpireTimeUtc");
        retVal = false;
    }

    retVal &= ValidateServiceBusAccountKeys(ServiceBusAccountKeys);
    retVal &= ValidateStorageAccountKeys(StorageAccountKeys);

    return retVal;
}

bool
GcsAccount::IsEmpty() const
{
    return (
        MaSigningPublicKeys.empty() &&
        SasKeysExpireTimeUtc.empty() &&
        ServiceBusAccountKeys.empty() &&
        StorageAccountKeys.empty()
        );
}

std::unordered_map<std::string, itemparser_t<GcsAccount>> GcsAccount::ParserMap = {
    { "MaSigningPublicKeys", [](const std::string & name, const web::json::value & value, GcsAccount& result)
      {
          if (!value.is_null()) {
              details::StringArrayParser parser(name, value);
              parser.Parse(result.MaSigningPublicKeys);
          }
      }
    },
    { "SasKeysExpireTimeUtc", [](const std::string & name, const web::json::value & value, GcsAccount& result)
      {
          if (!value.is_null()) {
              result.SasKeysExpireTimeUtc = GetStringFromJson(name, value);
          }
      }
    },
    { "ServiceBusAccountKeys" , [](const std::string & name, const web::json::value & value, GcsAccount& result)
      {
          if (!value.is_null()) {
              details::ObjectArrayParser<ServiceBusAccountKey> parser(name, value);
              parser.Parse(result.ServiceBusAccountKeys);
          }
      }
    },
    { "StorageAccountKeys", [](const std::string & name, const web::json::value & value, GcsAccount& result)
      {
          if (!value.is_null()) {
              details::ObjectArrayParser<StorageAccountKey> parser(name, value);
              parser.Parse(result.StorageAccountKeys);
          }
      }
    },
    { "TagId", [](const std::string & name, const web::json::value & value, GcsAccount& result)
      {
          result.TagId = GetStringFromJson(name, value);
      }
    }
};
