// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#pragma once
#ifndef _SAXPARSERBASE_HH_
#define _SAXPARSERBASE_HH_

#include <libxml/parser.h>

#include <string>
#include <unordered_map>
#include <stdexcept>

class SaxParserBaseException : public std::runtime_error
{
public:
	SaxParserBaseException(const std::string& message)
		: std::runtime_error(message)
	{}

    SaxParserBaseException(const char* message)
        : std::runtime_error(message)
    {}
};

/// <summary>
/// A simple base class for a specific SAX parser. User of this class
/// will derive a subclass from this and override necessary On...() methods
/// to achieve their desired SAX parsing. Currently not supporting all
/// the callbacks that LibXML2 supports. Should add all of them gradually.
/// This base class's callback handler methods are all empty so that users
/// don't have to implement all those methods, when they need only a few
/// of them.
/// </summary>
class SaxParserBase
{
public:
	typedef std::unordered_map<std::string, std::string> AttributeMap;

	SaxParserBase();
	virtual ~SaxParserBase();

	// Callbacks for various SAX parsing events
	virtual void OnStartDocument() {}
	virtual void OnEndDocument() {}
	virtual void OnComment(const std::string& comment) {}
	virtual void OnStartElement(const std::string& name, const AttributeMap& attributes) {}
	virtual void OnCharacters(const std::string& chars) {}
	virtual void OnEndElement(const std::string& name) {}

	virtual void OnWarning(const std::string& text) {}
	virtual void OnError(const std::string& text) {}
	virtual void OnFatalError(const std::string& text) {}

	virtual void OnCDataBlock(const std::string& text) {}

	/// <summary>
	/// Parse an entire XML document passed as a string.
	/// <param name="doc">The entire XML document passed as a string</param>
	/// </summary>
    void Parse(const std::string & doc);

    /// <summary>
    /// Parse a chunk of XML document passed as a string.
    /// This is needed so that a subclass don't have to use the
    /// libxml's C API to do the chunk parsing. We wanted to separate
    /// all I/Os from this class, so we'd need to provide this for
    /// any subclass.
    /// <param name="chunk">The XML chunk to be parsed, passed as a string</param>
    /// <param name="terminate">Indicates whether the passed chunk is the last one
    /// in the whole XML document</param>
    void ParseChunk(std::string chunk, bool terminate = false);

private:
	xmlParserCtxtPtr	m_ctxt;
};

#endif // _SAXPARSERBASE_HH_
