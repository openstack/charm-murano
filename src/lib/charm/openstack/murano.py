import charmhelpers.contrib.openstack.utils as ch_utils
import charmhelpers.core.hookenv as hookenv
import charms_openstack.charm
import charms_openstack.ip as os_ip

RC_FILE = '/root/novarc'


class MuranoCharm(charms_openstack.charm.HAOpenStackCharm):
    # Internal name of charm
    service_name = name = 'murano'

    # First release supported
    release = 'mitaka'

    # List of packages to install for this charm
    packages = ['murano-api', 'murano-engine', 'python-pymysql', 'python-apt']

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

    sync_cmd = ['murano-db-manage', '--config-file',
                '/etc/murano/murano.conf', 'upgrade']

    def __init__(self, release=None, **kwargs):
        """Custom initialiser for class
        If no release is passed, then the charm determines the release from the
        ch_utils.os_release() function.
        """
        if release is None:
            release = ch_utils.os_release('python-keystonemiddleware')
        super(MuranoCharm, self).__init__(release=release, **kwargs)

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
