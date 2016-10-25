import os
import socket
import subprocess

import charmhelpers.contrib.openstack.utils as ch_utils
import charmhelpers.core.hookenv as hookenv
import charms_openstack.charm
import charms_openstack.ip as os_ip

# import charms_openstack.sdn.odl as odl
# import charms_openstack.sdn.ovs as ovs

RC_FILE = '/root/novarc'

def get_environment(env):
    with open("/root/novarc", "r") as ins:
        for line in ins:
            k, v = line.replace('export', '').replace(" ", "").split('=')
            env[k] = v.strip()
    return env

def run_command(cmd):
    os_env = get_environment(os.environ.copy())
    subprocess.check_call(cmd, env=os_env)


def register_endpoints(keystone):
    """When the keystone interface connects, register this unit in the keystone
    catalogue.

    @param keystone: KeystoneRequires() interface class
    @returns: None
    """
    charm = MuranoCharm.singleton
    keystone.register_endpoints(charm.service_type,
                                charm.region,
                                charm.public_url,
                                charm.internal_url,
                                charm.admin_url)

def configure_ha_resources(hacluster):
    """Use the singleton from the MuranoCharm to run configure ha resources

    @param hacluster: OpenstackHAPeers() interface class
    @returns: None
    """
    MuranoCharm.singleton.configure_ha_resources(hacluster)


def restart_all():
    """Use the singleton from the MuranoCharm to restart all registered
    services

    @returns: None
    """
    MuranoCharm.singleton.restart_all()


def configure_ssl(keystone=None):
    """Use the singleton from the MuranoCharm to configure ssl

    @param keystone: KeystoneRequires() interface class
    @returns: None
    """
    MuranoCharm.singleton.configure_ssl(keystone)

def update_peers(hacluster):
    """Use the singleton from the MuranoCharm to update peers with detials
    of this unit

    @param hacluster: OpenstackHAPeers() interface class
    @returns: None
    """
    MuranoCharm.singleton.update_peers(hacluster)

def assess_status():
    """Just call the MuranoCharm.singleton.assess_status() command to update
    status on the unit.

    @returns: None
    """
    MuranoCharm.singleton.assess_status()

def render_novarc_config(interfaces_list):
    """Use the singleton from the MuranoCharm to run render_novarc_config

    @param interfaces_list: List of instances of interface classes.
    @returns: None
    """
    MuranoCharm.singleton.render_novarc_config(interfaces_list)

def import_io_murano():
    """Use the singleton from the MuranoCharm to run import io-murano
    package
    
    @returns: None
    """
    MuranoCharm.singleton.import_io_murano()


class MuranoCharm(charms_openstack.charm.HAOpenStackCharm):
    
    # Internal name of charm
    service_name = name = 'murano'

    # First release supported
    release = 'mitaka'

    # List of packages to install for this charm
    packages = ['murano-api', 'murano-engine', 'python-pymysql']
   
    # Init services the charm manages
    services = ['haproxy', 'murano-api', 'murano-engine']

    # Ports that need exposing.
    default_service = 'murano-api'
    api_ports = {
        'murano-api': {
            os_ip.PUBLIC: 8082,
            os_ip.ADMIN: 8082,
            os_ip.INTERNAL: 8082,
        }
    }

    service_type = 'murano'
    required_relations = ['shared-db', 'amqp', 'identity-service']

    restart_map = {
        '/etc/murano/murano.conf': services,
        RC_FILE: [''],
    }

    ha_resources = ['vips', 'haproxy']


    sync_cmd = ['murano-db-manage', '--config-file', '/etc/murano/murano.conf', 'upgrade']

    def __init__(self, release=None, **kwargs):
        """Custom initialiser for class
        If no release is passed, then the charm determines the release from the
        ch_utils.os_release() function.
        """
        if release is None:
            release = ch_utils.os_release('python-keystonemiddleware')
        super(MuranoCharm, self).__init__(release=release, **kwargs)

    def install(self):
        """Customise the installation, configure the source and then call the
        parent install() method to install the packages
        """
        self.configure_source()
        super(MuranoCharm, self).install()

    def render_novarc_config(self, interfaces_list):
        """Render novarc config to bootstrap Murano service

        @returns None
        """
        configs = [RC_FILE]
        self.render_with_interfaces(
            interfaces_list,
            configs=configs)
 

    def import_io_murano(self):
        """Install Core libary io-murano

        @returns None
        """
        io_murano_lib = "/usr/share/murano-common/io.murano.zip"
        if os.path.isfile(io_murano_lib):
           cmd = ['murano', 'package-import', io_murano_lib]
           run_command(cmd)
    

    def get_amqp_credentials(self):
        """Provide the default amqp username and vhost as a tuple.

        :returns (username, host): two strings to send to the amqp provider.
        """
        return (self.config['rabbit-user'], self.config['rabbit-vhost'])

    def get_database_setup(self):
        """Provide the default database credentials as a list of 3-tuples
    
        returns a structure of:
        [
            {'database': <database>,
            'username': <username>,
            'hostname': <hostname of this unit>
            'prefix': <the optional prefix for the database>, },
        ]
        
        :returns [{'database': ...}, ...]: credentials for multiple databases
        """
        return [
                dict(
                    database=self.config['database'],
                    username=self.config['database-user'],
                    hostname=hookenv.unit_private_ip(), )
        ]


