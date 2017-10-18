// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _GCSJSONPARSER_HH__
#define _GCSJSONPARSER_HH__

#include <string>
#include <vector>
#include <unordered_map>
#include <cpprest/json.h>

namespace mdsd
{

struct EventHubKey;
struct ServiceBusAccountKey;
struct StorageSasKey;
struct StorageAccountKey;
struct GcsAccount;

class GcsJsonParser {
public:
    GcsJsonParser(const std::string & jsonStr) : m_jsonStr(jsonStr) {}
    GcsJsonParser(const web::json::value & jsonObj) : m_jsonObj(jsonObj) {}

    // <summary>
    // Parse JSON string or JSON object and store the results to gcsAccount object.
    // </summary>
    // <param name="gcsAccount">To store parsed account information</param>
    // Return true if parsing succeeds; return false if any error.
    bool Parse(GcsAccount & gcsAccount);

private:
    std::string m_jsonStr;
    web::json::value m_jsonObj;
};

namespace details {

// This is the base class for all JSON parser classes.
class GcsJsonBaseParser {
public:
    // Constructor.
    // <param name="path">JSON path string. e.g. "/root/ServiceBusAccountKeys/EventHubKeys".
    // It is to locate items in JSON parsing.</param>
    // <param name="jsonObj">JSON object to be parsed</param>
    GcsJsonBaseParser(
        const std::string & path,
        const web::json::value & jsonObj
        ) :
        m_path(path),
        m_jsonObj(jsonObj)
    {
    }

    virtual ~GcsJsonBaseParser() = default;

protected:
    // Get actual JSON value type
    web::json::value::value_type GetActualType() const { return m_jsonObj.type(); }

    // Get expected JSON value type
    virtual web::json::value::value_type GetExpectedType() const { return web::json::value::Object; }

    const web::json::value& GetJson() const { return m_jsonObj; }

    virtual std::string GetPath() const { return m_path; }

    // Get path assuming the object is an array type.
    virtual std::string GetArrayPath(size_t i) const { return GetPath() + "[" + std::to_string(i) + "]"; }

    bool IsNull() const { return m_jsonObj.is_null(); }

    // Validate whether the JSON object has expected type. Throw exception if not.
    void CheckType() const;

    // Log message if unrecognized JSON name is found in JSON string.
    void LogMsgIfUnrecognized(const std::string & itemname) const;

private:
    std::string m_path;
    web::json::value m_jsonObj;
};

class EventHubKeysParser : public GcsJsonBaseParser {
public:
    EventHubKeysParser(const std::string & path, const web::json::value & jsonObj)
    : GcsJsonBaseParser(path, jsonObj) {}

    void Parse(std::unordered_map<std::string, EventHubKey>& ehkeys);
};

// To parse an array of json strings
class StringArrayParser : public GcsJsonBaseParser {
public:
    StringArrayParser(const std::string & path, const web::json::value & jsonObj)
        : GcsJsonBaseParser(path, jsonObj) {}

    void Parse(std::vector<std::string>& resultList);

protected:
    web::json::value::value_type GetExpectedType() const override { return web::json::value::Array; }
};

// A template to parse an array of json object type.
// The object type 'T' must have 'parser_type' defined.
template<typename T>
class ObjectArrayParser : public GcsJsonBaseParser {
public:
    ObjectArrayParser(const std::string & path, const web::json::value & jsonObj)
    : GcsJsonBaseParser(path, jsonObj) {}

    void Parse(std::vector<T>& resultList)
    {
        CheckType();
        auto & array = GetJson().as_array();

        for (size_t i = 0; i < array.size(); i++) {
            typename T::parser_type parser(GetArrayPath(i), array.at(i));
            T item;
            parser.Parse(item);
            resultList.push_back(std::move(item));
        }
    }

protected:
    web::json::value::value_type GetExpectedType() const override { return web::json::value::Array; }
};

// Parse a JSON object with type T
template<typename T>
class JsonObjectParser : public GcsJsonBaseParser {
public:
    JsonObjectParser(const std::string & path, const web::json::value & jsonObj)
    : GcsJsonBaseParser(path, jsonObj) {}

    void Parse(T& result) {
        CheckType();
        auto & jsonObj = GetJson().as_object();

        for (auto iter = jsonObj.cbegin(); iter != jsonObj.cend(); ++iter)
        {
            const auto & name = iter->first;
            const auto & value = iter->second;
            auto itempath = GetPath() + "/" + name;

            auto parserIter = T::ParserMap.find(name);
            if (parserIter == T::ParserMap.end()) {
                LogMsgIfUnrecognized(itempath);
            }
            else {
                parserIter->second(itempath, value, result);
            }
        }
    }
};

} // namespace details

} // namespace mdsd

#endif // _GCSJSONPARSER_HH__
