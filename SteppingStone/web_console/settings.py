#!/usr/bin/python

import os

ROOT_DIR = os.path.join('/root/azuredata')

# ------------------------- SHELLINABOX ----------------------------- #
SHELLINABOX_DOWNLOAD_URI = 'https://shellinabox.googlecode.com/files/'
SHELLINABOX_SRC = 'shellinabox-2.14'
SHELLINABOX_PREFIX = '/usr/local/shellinabox'
SHELLINABOX_CERT_DIR = '-c /var/lib/shellinabox'
SHELLINABOX_CERT_OWNER = '-u shellinabox -g shellinabox'
SHELLINABOX_DEFAULT_OPTS = '--user-css "Black on White:+/etc/shellinabox/options-enabled/00+Black on White.css,White On Black:-/etc/shellinabox/options-enabled/00_White On Black.css;Color Terminal:+/etc/shellinabox/options-enabled/01+Color Terminal.css,Monochrome:-/etc/shellinabox/options-enabled/01_Monochrome.css" --no-beep'
SHELLINABOX_PORT_RANGE = range(4200, 4204)

# ------------------------- GUACAMOLE ----------------------------- #
GUAC_CONF_DIR = '/etc/guacamole'
GUAC_LIB_DIR = '/var/lib/guacamole'
GUAC_CLASSPATH = os.path.join(GUAC_LIB_DIR, 'classpath')
GUAC_PROPERTIES = os.path.join(GUAC_CONF_DIR, 'guacamole.properties')

GUAC_VERSION = '0.9.2'
GUAC_SERVER_NAME = 'guacamole-server'
GUAC_CLIENT_NAME = 'guacamole-client'
GUAC_CLIENT_WAR_NAME = 'guacamole.war'

# no-auth configuration
EXTENSION_NOAUTH = 'guacamole-auth-noauth'
EXTENSION_NOAUTH_WITH_VERSION = EXTENSION_NOAUTH + '-' + GUAC_VERSION
NOAUTH_CONF = """auth-provider: net.sourceforge.guacamole.net.auth.noauth.NoAuthenticationProvider
noauth-config: /etc/guacamole/noauth-config.xml
"""
NOAUTH_CONF_FILE = 'noauth-config.xml'
NOAUTH_CONF_FILE_CONTENTS = """<configs>
    <config name="WEB RDP" protocol="rdp">
        <param name="hostname" value="localhost" />
        <param name="port" value="3389" />
    </config>
    <config name="WEB SSH" protocol="ssh">
        <param name="hostname" value="localhost" />
        <param name="port" value="22" />
    </config>
    <config name="WEB VNC" protocol="vnc">
        <param name="hostname" value="localhost" />
        <param name="port" value="5901" />
    </config>
</configs>
"""

# mysql-auth configuration
EXTENSION_MYSQLAUTH = 'guacamole-auth-mysql'
EXTENSION_MYSQLAUTH_WITH_VERSION = EXTENSION_MYSQLAUTH + '-' + GUAC_VERSION
MYSQLAUTH_CONF = """
"""

# Maybe Change
SRC_URI = 'https://binxia.blob.core.windows.net/stepping-stones-services/'
AZURE_VM_DOMAIN = '.cloudapp.net'
