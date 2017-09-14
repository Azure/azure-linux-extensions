// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>

#include "BodyOnlyXmlParser.hh"
#include "MdsException.hh"

using namespace mdsd::details;

void
BodyOnlyXmlParser::ParseFile(std::string xmlFilePath)
{
    m_xmlFilePath = std::move(xmlFilePath);

    std::ifstream infile{m_xmlFilePath};
    if (!infile) {
        std::ostringstream strm;
        strm << "Failed to open file '" << m_xmlFilePath << "'.";
        throw MDSEXCEPTION(strm.str());
    }

    std::string line;
    while(std::getline(infile, line)) {
        ParseChunk(line);
    }

    if (!infile.eof()) {
        std::ostringstream strm;
        strm << "Failed to parse file '" << m_xmlFilePath << "': ";
        if (infile.bad()) {
            strm << "Corrupted stream.";
        }
        else if (infile.fail()) {
            strm << "IO operation failed.";
        }
        else {
            strm << "std::getline() returned 0 for unknown reason.";
        }
        throw MDSEXCEPTION(strm.str());
    }
}

void
BodyOnlyXmlParser::OnCharacters(const std::string& chars)
{
    bool isEmptyOrWhiteSpace = std::all_of(chars.cbegin(), chars.cend(), ::isspace);
    if (!isEmptyOrWhiteSpace) {
        m_body.append(chars);
    }
}
