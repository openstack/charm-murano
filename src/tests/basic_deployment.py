import subprocess
import amulet
import json
import time

import muranoclient.client as murano_client
from keystoneclient import session as keystone_session
from keystoneclient.auth import identity as keystone_identity

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG,
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(DEBUG)


class MuranoBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic murano deployment."""

    def __init__(self, series, openstack=None, source=None, stable=False):
        """Deploy the entire test environment."""
        super(MuranoBasicDeployment, self).__init__(series, openstack,
                                                    source, stable)
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()

        u.log.info('Waiting on extended status checks...')
        exclude_services = []
        self._auto_wait_for_status(exclude_services=exclude_services)

        self.d.sentry.wait()
        self._initialize_tests()

    def _add_services(self):
        """Add services

           Add the services that we're testing, where murano is local,
           and the rest of the service are from lp branches that are
           compatible with the local charm (e.g. stable or next).
           """
        this_service = {'name': 'murano'}
        other_services = [
            {'name': 'percona-cluster', 'constraints': {'mem': '3072M'}},
            {'name': 'rabbitmq-server'},
            {'name': 'keystone'},
        ]
        super(MuranoBasicDeployment, self)._add_services(this_service,
                                                         other_services)

    def _add_relations(self):
        """Add all of the relations for the services."""
        relations = {
            'murano:shared-db': 'percona-cluster:shared-db',
            'murano:amqp': 'rabbitmq-server:amqp',
            'murano:identity-service': 'keystone:identity-service',
            'keystone:shared-db': 'percona-cluster:shared-db',

        }
        super(MuranoBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        keystone_config = {
            'admin-password': 'openstack',
            'admin-token': 'ubuntutesting'
        }
        pxc_config = {
            'dataset-size': '25%',
            'max-connections': 1000,
            'root-password': 'ChangeMe123',
            'sst-password': 'ChangeMe123',
        }
        configs = {
            'keystone': keystone_config,
            'percona-cluster': pxc_config,
        }
        super(MuranoBasicDeployment, self)._configure_services(configs)

    def _get_token(self):
        return self.keystone.service_catalog.catalog['token']['id']

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.murano_sentry = self.d.sentry['murano'][0]
        self.pxc_sentry = self.d.sentry['percona-cluster'][0]
        self.keystone_sentry = self.d.sentry['keystone'][0]
        self.rabbitmq_sentry = self.d.sentry['rabbitmq-server'][0]
        u.log.debug('openstack release val: {}'.format(
            self._get_openstack_release()))
        u.log.debug('openstack release str: {}'.format(
            self._get_openstack_release_string()))

        # Authenticate admin with keystone endpoint
        self.keystone = u.authenticate_keystone_admin(self.keystone_sentry,
                                                      user='admin',
                                                      password='openstack',
                                                      tenant='admin')

        # Authenticate admin with murano endpoint
        murano_ep = self.keystone.service_catalog.url_for(
            service_type='application-catalog',
            endpoint_type='publicURL')

        keystone_ep = self.keystone.service_catalog.url_for(
            service_type='identity',
            endpoint_type='publicURL')

        auth = keystone_identity.V2Token(auth_url=keystone_ep,
                                         token=self.keystone.auth_token)
        sess = keystone_session.Session(auth=auth)
        self.murano = murano_client.Client(version=1, session=sess,
                                           endpoint_override=murano_ep)

    def _run_action(self, unit_id, action, *args):
        command = ["juju", "action", "do", "--format=json", unit_id, action]
        command.extend(args)
        print("Running command: %s\n" % " ".join(command))
        output = subprocess.check_output(command)
        output_json = output.decode(encoding="UTF-8")
        data = json.loads(output_json)
        action_id = data[u'Action queued with id']
        return action_id

    def _wait_on_action(self, action_id):
        command = ["juju", "action", "fetch", "--format=json", action_id]
        while True:
            try:
                output = subprocess.check_output(command)
            except Exception as e:
                print(e)
                return False
            output_json = output.decode(encoding="UTF-8")
            data = json.loads(output_json)
            if data[u"status"] == "completed":
                return True
            elif data[u"status"] == "failed":
                return False
            time.sleep(2)

    def test_100_services(self):
        """Verify the expected services are running on the corresponding
           service units."""
        u.log.debug('Checking system services on units...')

        murano_svcs = [
            'murano-api', 'murano-engine'
        ]

        service_names = {
            self.murano_sentry: murano_svcs,
        }

        ret = u.validate_services_by_name(service_names)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

        u.log.debug('OK')

    def test_110_service_catalog(self):
        """Verify that the service catalog endpoint data is valid."""
        u.log.debug('Checking keystone service catalog data...')
        endpoint_check = {
            'adminURL': u.valid_url,
            'id': u.not_null,
            'region': 'RegionOne',
            'publicURL': u.valid_url,
            'internalURL': u.valid_url
        }
        expected = {
            'application-catalog': [endpoint_check],
        }
        actual = self.keystone.service_catalog.get_endpoints()

        ret = u.validate_svc_catalog_endpoint_data(expected, actual)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

        u.log.debug('OK')

    def test_114_murano_api_endpoint(self):
        """Verify the murano api endpoint data."""
        u.log.debug('Checking murano api endpoint data...')
        endpoints = self.keystone.endpoints.list()
        u.log.debug(endpoints)
        admin_port = internal_port = public_port = '8082'
        expected = {'id': u.not_null,
                    'region': 'RegionOne',
                    'adminurl': u.valid_url,
                    'internalurl': u.valid_url,
                    'publicurl': u.valid_url,
                    'service_id': u.not_null}

        ret = u.validate_endpoint_data(endpoints, admin_port, internal_port,
                                       public_port, expected)
        if ret:
            message = 'murano endpoint: {}'.format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_200_murano_identity_relation(self):
        """Verify the murano to keystone identity-service relation data"""
        u.log.debug('Checking murano to keystone identity-service '
                    'relation data...')
        unit = self.murano_sentry
        relation = ['identity-service', 'keystone:identity-service']
        murano_relation = unit.relation('identity-service',
                                        'keystone:identity-service')
        murano_ip = murano_relation['private-address']
        murano_endpoint = "http://%s:8082" % (murano_ip)

        expected = {
            'admin_url': murano_endpoint,
            'internal_url': murano_endpoint,
            'private-address': murano_ip,
            'public_url': murano_endpoint,
            'region': 'RegionOne',
            'service': 'murano',
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('murano identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_201_keystone_murano_identity_relation(self):
        """Verify the keystone to murano identity-service relation data"""
        u.log.debug('Checking keystone:murano identity relation data...')
        unit = self.keystone_sentry
        relation = ['identity-service', 'murano:identity-service']
        id_relation = unit.relation('identity-service',
                                    'murano:identity-service')
        id_ip = id_relation['private-address']
        expected = {
            'admin_token': 'ubuntutesting',
            'auth_host': id_ip,
            'auth_port': "35357",
            'auth_protocol': 'http',
            'private-address': id_ip,
            'service_host': id_ip,
            'service_password': u.not_null,
            'service_port': "5000",
            'service_protocol': 'http',
            'service_tenant': 'services',
            'service_tenant_id': u.not_null,
            'service_username': 'murano',
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('keystone identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_203_murano_amqp_relation(self):
        """Verify the murano to rabbitmq-server amqp relation data"""
        u.log.debug('Checking murano:rabbitmq amqp relation data...')
        unit = self.murano_sentry
        relation = ['amqp', 'rabbitmq-server:amqp']
        expected = {
            'username': 'murano',
            'private-address': u.valid_ip,
            'vhost': 'openstack'
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('murano amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_204_amqp_murano_relation(self):
        """Verify the rabbitmq-server to murano amqp relation data"""
        u.log.debug('Checking rabbitmq:murano amqp relation data...')
        unit = self.rabbitmq_sentry
        relation = ['amqp', 'murano:amqp']
        expected = {
            'hostname': u.valid_ip,
            'private-address': u.valid_ip,
            'password': u.not_null,
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('rabbitmq amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

        u.log.debug('OK')

    def test_900_restart_on_config_change(self):
        """Verify that the specified services are restarted when the config
           is changed.
           """
        sentry = self.murano_sentry
        juju_service = 'murano'

        # Expected default and alternate values
        set_default = {'debug': 'False'}
        set_alternate = {'debug': 'True'}

        # Services which are expected to restart upon config change,
        # and corresponding config files affected by the change
        conf_file = '/etc/murano/murano.conf'
        services = {
            'murano-api': conf_file,
            'murano-engine': conf_file,
        }

        # Make config change, check for service restarts
        u.log.debug('Making config change on {}...'.format(juju_service))
        mtime = u.get_sentry_time(sentry)
        self.d.configure(juju_service, set_alternate)

        sleep_time = 40
        for s, conf_file in services.iteritems():
            u.log.debug("Checking that service restarted: {}".format(s))
            if not u.validate_service_config_changed(sentry, mtime, s,
                                                     conf_file,
                                                     retry_count=4,
                                                     retry_sleep_time=20,
                                                     sleep_time=sleep_time):
                self.d.configure(juju_service, set_default)
                msg = "service {} didn't restart after config change".format(s)
                amulet.raise_status(amulet.FAIL, msg=msg)
            sleep_time = 0

        self.d.configure(juju_service, set_default)
        u.log.debug('OK')

    def _test_910_pause_and_resume(self):
        """The services can be paused and resumed. """
        u.log.debug('Checking pause and resume actions...')
        unit_name = "murano/0"
        unit = self.d.sentry['murano'][0]
        juju_service = 'murano'

        assert u.status_get(unit)[0] == "active"

        action_id = self._run_action(unit_name, "pause")
        assert self._wait_on_action(action_id), "Pause action failed."
        assert u.status_get(unit)[0] == "maintenance"

        # trigger config-changed to ensure that services are still stopped
        u.log.debug("Making config change on murano ...")
        self.d.configure(juju_service, {'debug': 'True'})
        assert u.status_get(unit)[0] == "maintenance"
        self.d.configure(juju_service, {'debug': 'False'})
        assert u.status_get(unit)[0] == "maintenance"

        action_id = self._run_action(unit_name, "resume")
        assert self._wait_on_action(action_id), "Resume action failed."
        assert u.status_get(unit)[0] == "active"
        u.log.debug('OK')
