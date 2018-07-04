#!/usr/bin/env python2

#
# Copyright (C) Microsoft Corporation, All rights reserved.

"""Urllib2 HttpClient."""

import httplib
import socket
import time
import traceback
import urllib2

from httpclient import *

PY_MAJOR_VERSION = 0
PY_MINOR_VERSION = 1
PY_MICRO_VERSION = 2

SSL_MODULE_NAME = "ssl"

# On some system the ssl module might be missing
try:
    import ssl
except ImportError:
    ssl = None


class HttpsClientHandler(urllib2.HTTPSHandler):
    """Https handler to enable attaching cert/key to request. Also used to disable strict cert verification for
    testing.
    """

    def __init__(self, cert_path, key_path, insecure=False):
        self.cert_path = cert_path
        self.key_path = key_path

        ssl_context = None
        if insecure and SSL_MODULE_NAME in sys.modules and (sys.version_info[PY_MAJOR_VERSION] == 2 and
                                                                    sys.version_info[PY_MINOR_VERSION] >= 7 and
                                                                    sys.version_info[PY_MICRO_VERSION] >= 9):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        urllib2.HTTPSHandler.__init__(self, context=ssl_context)  # Context can be None here

    def https_open(self, req):
        return self.do_open(self.get_https_connection, req, context=self._context)

    def get_https_connection(self, host, context=None, timeout=180):
        """urllib2's AbstractHttpHandler will invoke this method with the host/timeout parameter. See urllib2's
        AbstractHttpHandler for more details.

        Args:
            host    : string        , the host.
            context : ssl_context   , the ssl context.
            timeout : int           , the timeout value in seconds.

        Returns:
            An HttpsConnection
        """
        socket.setdefaulttimeout(180)
        if self.cert_path is None or self.key_path is None:
            return httplib.HTTPSConnection(host, timeout=timeout, context=context)
        else:
            return httplib.HTTPSConnection(host, cert_file=self.cert_path, key_file=self.key_path, timeout=timeout,
                                           context=context)


def request_retry_handler(func):
    def decorated_func(*args, **kwargs):
        max_retry_count = 3
        for iteration in range(0, max_retry_count, 1):
            try:
                ret = func(*args, **kwargs)
                return ret
            except Exception, exception:
                if iteration >= max_retry_count - 1:
                    raise RetryAttemptExceededException(traceback.format_exc())
                elif SSL_MODULE_NAME in sys.modules:
                    if type(exception).__name__ == 'SSLError':
                        time.sleep(5 + iteration)
                        continue
                raise exception
    return decorated_func


class Urllib2HttpClient(HttpClient):
    """Urllib2 http client. Inherits from HttpClient.

    Targets:
        [2.7.9 - 2.7.9+] only due to the lack of strict certificate verification prior to this version.

    Implements the following method common to all classes inheriting HttpClient.
        get     (url, headers)
        post    (url, headers, data)
    """

    def __init__(self, cert_path, key_path, insecure=False, proxy_configuration=None):
        HttpClient.__init__(self, cert_path, key_path, insecure, proxy_configuration)

    @request_retry_handler
    def issue_request(self, url, headers, method=None, data=None):
        """Issues a GET request to the provided url and using the provided headers.

        Args:
            url     : string    , the url.
            headers : dictionary, contains the headers key value pair.
            data    : string    , contains the serialized request body.

        Returns:
            A RequestResponse
            :param method:
        """
        https_handler = HttpsClientHandler(self.cert_path, self.key_path, self.insecure)
        opener = urllib2.build_opener(https_handler)
        if self.proxy_configuration is not None:
            proxy_handler = urllib2.ProxyHandler({'http': self.proxy_configuration,
                                                  'https': self.proxy_configuration})
            opener.add_handler(proxy_handler)
        req = urllib2.Request(url, data=data, headers=headers)
        req.get_method = lambda: method
        response = opener.open(req, timeout=30)
        opener.close()
        https_handler.close()

        return response

    def get(self, url, headers=None):
        """Issues a GET request to the provided url and using the provided headers.

        Args:
            url     : string    , the url.
            headers : dictionary, contains the headers key value pair.

        Returns:
            An http_response
        """
        headers = self.merge_headers(self.default_headers, headers)

        try:
            response = self.issue_request(url, headers=headers, method=self.GET)
        except urllib2.HTTPError:
            exception_type, error = sys.exc_info()[:2]
            return RequestResponse(error.code)

        return RequestResponse(response.getcode(), response.read())

    def post(self, url, headers=None, data=None):
        """Issues a POST request to the provided url and using the provided headers.

        Args:
            url     : string    , the url.
            headers : dictionary, contains the headers key value pair.
            data    : dictionary, contains the non-serialized request body.

        Returns:
            A RequestResponse
        """
        headers = self.merge_headers(self.default_headers, headers)

        if data is None:
            serial_data = ""
        else:
            serial_data = self.json.dumps(data)
            headers.update({self.CONTENT_TYPE_HEADER_KEY: self.APP_JSON_HEADER_VALUE})

        try:
            response = self.issue_request(url, headers=headers, method=self.POST, data=serial_data)
        except urllib2.HTTPError:
            exception_type, error = sys.exc_info()[:2]
            return RequestResponse(error.code)

        return RequestResponse(response.getcode(), response.read())

    def put(self, url, headers=None, data=None):
        """Issues a PUT request to the provided url and using the provided headers.

        Args:
            url     : string    , the url.
            headers : dictionary, contains the headers key value pair.
            data    : dictionary, contains the non-serialized request body.

        Returns:
            A RequestResponse
        """
        headers = self.merge_headers(self.default_headers, headers)

        if data is None:
            serial_data = ""
        else:
            serial_data = self.json.dumps(data)
            headers.update({self.CONTENT_TYPE_HEADER_KEY: self.APP_JSON_HEADER_VALUE})

        try:
            response = self.issue_request(url, headers=headers, method=self.PUT, data=serial_data)
        except urllib2.HTTPError:
            exception_type, error = sys.exc_info()[:2]
            return RequestResponse(error.code)

        return RequestResponse(response.getcode(), response.read())

    def delete(self, url, headers=None, data=None):
        """Issues a DELETE request to the provided url and using the provided headers.

        Args:
            url     : string    , the url.
            headers : dictionary, contains the headers key value pair.
            data    : dictionary, contains the non-serialized request body.

        Returns:
            A RequestResponse
        """
        headers = self.merge_headers(self.default_headers, headers)

        if data is None:
            serial_data = ""
        else:
            serial_data = self.json.dumps(data)
            headers.update({self.CONTENT_TYPE_HEADER_KEY: self.APP_JSON_HEADER_VALUE})

        try:
            response = self.issue_request(url, headers=headers, method=self.DELETE, data=serial_data)
        except urllib2.HTTPError:
            exception_type, error = sys.exc_info()[:2]
            return RequestResponse(error.code)

        return RequestResponse(response.getcode(), response.read())
