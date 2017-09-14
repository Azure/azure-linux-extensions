// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "SaxParserBase.hh"

#include <cassert>
#include <exception>
#include <sstream>
extern "C" {
#include <stdarg.h>
#include <stdio.h>
}

///////////////////////////////////////////////////////////////////////
// SAX callback dispatchers that are registered for every SaxParserBase
// instance, which will call the actual callbacks in the instance.

static void OnStartDocumentCallback(void* userData)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

	parser->OnStartDocument();
}

static void OnEndDocumentCallback(void* userData)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

	parser->OnEndDocument();
}

static void OnCommentCallback(void* userData, const xmlChar* comment)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

    const std::string commentStr((comment == nullptr) ? "" : reinterpret_cast<const char*>(comment));

    parser->OnComment(commentStr);
}

static void OnStartElementCallback(
    void*           userData,
    const xmlChar*  localname,
    const xmlChar** attributes
)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

    std::string name(reinterpret_cast<const char*>(localname));
    SaxParserBase::AttributeMap attrs;

    while (attributes != nullptr && *attributes != nullptr) {
    	auto key = reinterpret_cast<const char*>(attributes[0]);
    	auto value = reinterpret_cast<const char*>(attributes[1]);

    	auto retval = attrs.emplace(key, value);
    	if (!retval.second) {
    	    std::ostringstream oss;
    	    oss << "An extra instance of attribute \"" << key
    	        << "\" in element \"" << name << "\" was seen and ignored";
    	    parser->OnWarning(oss.str());
    	}
    	attributes += 2;
    }

    parser->OnStartElement(name, attrs);
}

static void OnCharactersCallback(
	void*          userData,
	const xmlChar* chars,
	int len
)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

    const std::string charsStr(reinterpret_cast<const char*>(chars), static_cast<size_t>(len));

    parser->OnCharacters(charsStr);
}

static void OnEndElementCallback(
    void*          userData,
    const xmlChar* localname
)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

    const std::string name(reinterpret_cast<const char*>(localname));

    parser->OnEndElement(name);
}

static constexpr size_t MESSAGE_BUFFER_SIZE = 512;

static void OnWarningCallback(void* userData, const char* msg, ...)
{
	auto parser = static_cast<SaxParserBase*>(userData);
	assert(nullptr != parser);

	char buf[MESSAGE_BUFFER_SIZE];
	va_list arglist;

	va_start(arglist, msg);
	vsnprintf(buf, MESSAGE_BUFFER_SIZE, msg, arglist);
	va_end(arglist);

	const std::string warning(buf);

	parser->OnWarning(warning);
}

static void OnErrorCallback(void* userData, const char* msg, ...)
{
	auto parser = static_cast<SaxParserBase*>(userData);
	assert(nullptr != parser);

	char buf[MESSAGE_BUFFER_SIZE];
	va_list arglist;

	va_start(arglist, msg);
	vsnprintf(buf, MESSAGE_BUFFER_SIZE, msg, arglist);
	va_end(arglist);

	const std::string error(buf);

	parser->OnError(error);
}

static void OnFatalErrorCallback(void* userData, const char* msg, ...)
{
	auto parser = static_cast<SaxParserBase*>(userData);
	assert(nullptr != parser);

	char buf[MESSAGE_BUFFER_SIZE];
	va_list arglist;

	va_start(arglist, msg);
	vsnprintf(buf, MESSAGE_BUFFER_SIZE, msg, arglist);
	va_end(arglist);

	const std::string fatalError(buf);

	parser->OnFatalError(fatalError);
}

static void OnCDataBlockCallback(
	void*          userData,
	const xmlChar* chars,
	int len
)
{
	auto parser = static_cast<SaxParserBase*>(userData);
    assert(nullptr != parser);

    const std::string cdata(reinterpret_cast<const char*>(chars), static_cast<size_t>(len));

    parser->OnCDataBlock(cdata);
}

///////////////// End of SAX callback dispatchers /////////////////////


///////////////////////////////////////////////////////////////////////
// Helper function to get the xmlSAXHandler pointer with the callback
// dispatcher functions already registered.

static xmlSAXHandler* GetSaxHandler()
{
	static xmlSAXHandler saxHandler = {
		    nullptr, // internalSubset;
		    nullptr, // isStandalone;
		    nullptr, // hasInternalSubset;
		    nullptr, // hasExternalSubset;
		    nullptr, // resolveEntity;
		    nullptr, // getEntity;
		    nullptr, // entityDecl;
		    nullptr, // notationDecl;
		    nullptr, // attributeDecl;
		    nullptr, // elementDecl;
		    nullptr, // unparsedEntityDecl;
		    nullptr, // setDocumentLocator;
		    OnStartDocumentCallback, // startDocument;
		    OnEndDocumentCallback,   // endDocument;
		    OnStartElementCallback,  // startElement;
		    OnEndElementCallback,    // endElement;
		    nullptr, // reference;
		    OnCharactersCallback,    // characters;
		    nullptr, // ignorableWhitespace;
		    nullptr, // processingInstruction;
		    OnCommentCallback,       // comment;
		    OnWarningCallback,       // warning;
		    OnErrorCallback,         // error;
		    OnFatalErrorCallback,    // fatalError; /* unused error() get all the errors */
		    nullptr, // getParameterEntity;
		    OnCDataBlockCallback,    // cdataBlock;
		    nullptr, // externalSubset;
		    0,       // initialized;
		    /* The following fields are extensions available only on version 2 */
		    nullptr, // _private;
		    nullptr, // startElementNs;
		    nullptr, // endElementNs;
		    nullptr  // serror;
	};

	return &saxHandler;
}

///////////////////////////////////////////////////////////////////////
// SaxParserBase implementation

SaxParserBase::SaxParserBase()
    : m_ctxt(nullptr)
{
    xmlSAXHandlerPtr saxHander = GetSaxHandler();

    m_ctxt = xmlCreatePushParserCtxt(saxHander, NULL, NULL, 0, NULL);

    if (m_ctxt == nullptr)
    {
        throw SaxParserBaseException("Failed to create Xml parser context");
    }

    // The instance pointer should be saved so that the callback
    // dispatcher functions can route the calls to the proper
    // SaxParserBase instance.
    m_ctxt->userData = this;
}

SaxParserBase::~SaxParserBase()
{
	if (m_ctxt != nullptr)
	{
		xmlFreeParserCtxt(m_ctxt);
	}
}

#define MAX_SAX_CHUNK_SIZE 1024

void SaxParserBase::Parse(const std::string & doc)
{
    if (m_ctxt == nullptr) {
        throw SaxParserBaseException("Xml parser context wasn't created correctly at the construction time");
    }

    const char* buf = doc.c_str();
    size_t totalLen = doc.length();
    size_t remainingLen = totalLen;

    while (remainingLen > 0) {
    	const size_t chunkSize = std::min((size_t)MAX_SAX_CHUNK_SIZE, remainingLen);
    	const int terminate = (chunkSize == remainingLen);
    	int result = xmlParseChunk(m_ctxt, buf, (int)chunkSize, terminate);
    	if (result) {
    		const int offsetBegin = totalLen - remainingLen;
    		const int offsetEnd = offsetBegin + (int)chunkSize;

    		std::ostringstream oss;

    		oss << "xmlParseChunk error between offset " << offsetBegin
    			<< " and " << offsetEnd << " (return code = " << result << ")";
    		this->OnError(oss.str());

    		return;
    	}
    	remainingLen -= chunkSize;
    	buf += chunkSize;
    }
}

void SaxParserBase::ParseChunk(std::string chunk, bool terminate)
{
	if (m_ctxt == nullptr) {
		throw SaxParserBaseException("Xml parser context wasn't created correctly at the construction time");
	}

	int result = xmlParseChunk(m_ctxt, chunk.c_str(), (int)chunk.length(), terminate);
	if (result) {
		std::ostringstream oss;

		oss << "xmlParseChunk error (return code = " << result << ")";
		this->OnError(oss.str());
	}
}
