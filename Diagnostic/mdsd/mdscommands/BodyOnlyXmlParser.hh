// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef __BODYONLYXMLPARSER__HH__
#define __BODYONLYXMLPARSER__HH__

#include <iostream>
#include <string>
#include "SaxParserBase.hh"

namespace mdsd { namespace details
{

/// <summary>
/// This is a simple XML parser. It will parse the XML body section only.
/// The XML attributes are not parsed.
/// </summary>
class BodyOnlyXmlParser : public SaxParserBase
{
public:
    BodyOnlyXmlParser() = default;
    ~BodyOnlyXmlParser() = default;

    /// <summary> Parse given xml file </summary>
    virtual void ParseFile(std::string xmlFilePath);

    std::string&& MoveBody() { return std::move(m_body); }
    virtual std::string GetFilePath() const { return m_xmlFilePath; }

private:
    void OnStartElement(const std::string& name, const AttributeMap& attributes) override { m_body.clear(); }
    void OnEndElement(const std::string& name) override {}
    void OnCharacters(const std::string& chars) override;
    void OnCDataBlock(const std::string& text) override { m_body.append(text); }

private:
    std::string m_xmlFilePath;
    std::string m_body;
};

} // namespace details
} // namespace mdsd

#endif // __BODYONLYXMLPARSER__HH__
