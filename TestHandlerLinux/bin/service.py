#!/usr/bin/env python

import imp

"""
service example
"""
resources_dir = 'RESOURCES_PATH'
mypydoc=imp.load_source('mypydoc',resources_dir+'/mypydoc.py')
mypydoc.cli()
