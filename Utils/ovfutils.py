import re
import os
import base64
import xml.dom.minidom
import xml.sax.saxutils
import Utils.extensionutils as ext_utils
import Utils.constants as constants
import Utils.logger as logger


def get_node_text_data(a):
    """
    Filter non-text nodes from DOM tree
    """
    for b in a.childNodes:
        if b.nodeType == b.TEXT_NODE:
            return b.data


def translate_custom_data(data, configuration):
    """
    Translate the custom data from a Base64 encoding. Default to no-op.
    """
    data_to_decode = configuration.get("Provisioning.DecodeCustomData")
    if data_to_decode is not None and data_to_decode.lower().startswith("y"):
        return base64.b64decode(data)
    return data


class OvfEnv(object):
    """
    Read, and process provisioning info from provisioning file OvfEnv.xml
    """

    #
    # <?xml version="1.0" encoding="utf-8"?>
    # <Environment xmlns="http://schemas.dmtf.org/ovf/environment/1"
    # xmlns:oe="http://schemas.dmtf.org/ovf/environment/1" xmlns:wa="http://schemas.microsoft.com/windowsazure"
    # xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    #    <wa:ProvisioningSection>
    #      <wa:Version>1.0</wa:Version>
    #      <LinuxProvisioningConfigurationSet
    #      xmlns="http://schemas.microsoft.com/windowsazure" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
    #        <ConfigurationSetType>LinuxProvisioningConfiguration</ConfigurationSetType>
    #        <HostName>HostName</HostName>
    #        <UserName>UserName</UserName>
    #        <UserPassword>UserPassword</UserPassword>
    #        <DisableSshPasswordAuthentication>false</DisableSshPasswordAuthentication>
    #        <SSH>
    #          <PublicKeys>
    #            <PublicKey>
    #              <Fingerprint>EB0C0AB4B2D5FC35F2F0658D19F44C8283E2DD62</Fingerprint>
    #              <Path>$HOME/UserName/.ssh/authorized_keys</Path>
    #            </PublicKey>
    #          </PublicKeys>
    #          <KeyPairs>
    #            <KeyPair>
    #              <Fingerprint>EB0C0AB4B2D5FC35F2F0658D19F44C8283E2DD62</Fingerprint>
    #              <Path>$HOME/UserName/.ssh/id_rsa</Path>
    #            </KeyPair>
    #          </KeyPairs>
    #        </SSH>
    #      </LinuxProvisioningConfigurationSet>
    #    </wa:ProvisioningSection>
    # </Environment>
    #
    def __init__(self):
        """
        Reset members.
        """
        self.WaNs = "http://schemas.microsoft.com/windowsazure"
        self.OvfNs = "http://schemas.dmtf.org/ovf/environment/1"
        self.MajorVersion = 1
        self.MinorVersion = 0
        self.ComputerName = None
        self.AdminPassword = None
        self.UserName = None
        self.UserPassword = None
        self.CustomData = None
        self.DisableSshPasswordAuthentication = True
        self.SshPublicKeys = []
        self.SshKeyPairs = []

    # this is a static function to return an instance of  OfvEnv
    @staticmethod
    def parse(xml_text, configuration, is_deprovision=False, write_custom_data=True):
        """
        Parse xml tree, retrieving user and ssh key information.
        Return self.
        """
        ovf_env = OvfEnv()
        if xml_text is None:
            return None
        logger.log_if_verbose(re.sub("UserPassword>.*?<", "UserPassword>*<", xml_text))
        try:
            dom = xml.dom.minidom.parseString(xml_text)
        except (TypeError, xml.parsers.expat.ExpatError):
            # when the input is of unexpected type or invalid xml
            return None
        if len(dom.getElementsByTagNameNS(ovf_env.OvfNs, "Environment")) != 1:
            logger.error("Unable to parse OVF XML.")
        section = None
        newer = False
        for p in dom.getElementsByTagNameNS(ovf_env.WaNs, "ProvisioningSection"):
            for n in p.childNodes:
                if n.localName == "Version":
                    verparts = get_node_text_data(n).split('.')
                    major = int(verparts[0])
                    minor = int(verparts[1])
                    if major > ovf_env.MajorVersion:
                        newer = True
                    if major != ovf_env.MajorVersion:
                        break
                    if minor > ovf_env.MinorVersion:
                        newer = True
                    section = p
        if newer:
            logger.warning(
                "Newer provisioning configuration detected. Please consider updating waagent.")
        if section is None:
            logger.error(
                "Could not find ProvisioningSection with major version=" + str(ovf_env.MajorVersion))
            return None
        ovf_env.ComputerName = get_node_text_data(section.getElementsByTagNameNS(ovf_env.WaNs, "HostName")[0])
        ovf_env.UserName = get_node_text_data(section.getElementsByTagNameNS(ovf_env.WaNs, "UserName")[0])
        if is_deprovision:
            return ovf_env
        try:
            ovf_env.UserPassword = get_node_text_data(section.getElementsByTagNameNS(ovf_env.WaNs, "UserPassword")[0])
        except (KeyError, ValueError, AttributeError, IndexError):
            pass

        if write_custom_data:
            try:
                cd_section = section.getElementsByTagNameNS(ovf_env.WaNs, "CustomData")
                if len(cd_section) > 0:
                    ovf_env.CustomData = get_node_text_data(cd_section[0])
                    if len(ovf_env.CustomData) > 0:
                        ext_utils.set_file_contents(constants.LibDir + '/CustomData', bytearray(
                            translate_custom_data(ovf_env.CustomData, configuration)))
                        logger.log('Wrote ' + constants.LibDir + '/CustomData')
                    else:
                        logger.error('<CustomData> contains no data!')
            except Exception as e:
                logger.error(str(e) + ' occured creating ' + constants.LibDir + '/CustomData')
        
        disable_ssh_passwd = section.getElementsByTagNameNS(ovf_env.WaNs, "DisableSshPasswordAuthentication")
        if len(disable_ssh_passwd) != 0:
            ovf_env.DisableSshPasswordAuthentication = (get_node_text_data(disable_ssh_passwd[0]).lower() == "true")
        for pkey in section.getElementsByTagNameNS(ovf_env.WaNs, "PublicKey"):
            logger.log_if_verbose(repr(pkey))
            fp = None
            path = None
            for c in pkey.childNodes:
                if c.localName == "Fingerprint":
                    fp = get_node_text_data(c).upper()
                    logger.log_if_verbose(fp)
                if c.localName == "Path":
                    path = get_node_text_data(c)
                    logger.log_if_verbose(path)
            ovf_env.SshPublicKeys += [[fp, path]]
        for keyp in section.getElementsByTagNameNS(ovf_env.WaNs, "KeyPair"):
            fp = None
            path = None
            logger.log_if_verbose(repr(keyp))
            for c in keyp.childNodes:
                if c.localName == "Fingerprint":
                    fp = get_node_text_data(c).upper()
                    logger.log_if_verbose(fp)
                if c.localName == "Path":
                    path = get_node_text_data(c)
                    logger.log_if_verbose(path)
            ovf_env.SshKeyPairs += [[fp, path]]
        return ovf_env

    def prepare_dir(self, filepath, distro):
        """
        Create home dir for self.UserName
        Change owner and return path.
        """
        home = distro.get_home()
        # Expand HOME variable if present in path
        path = os.path.normpath(filepath.replace("$HOME", home))
        if (not path.startswith("/")) or path.endswith("/"):
            return None
        dir_name = path.rsplit('/', 1)[0]
        if dir_name != "":
            ext_utils.create_dir(dir_name, "root", 0o700)
            if path.startswith(os.path.normpath(home + "/" + self.UserName + "/")):
                ext_utils.create_dir(dir_name, self.UserName, 0o700)
        return path
