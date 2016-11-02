# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import charms_openstack.charm as charm
import charms.reactive as reactive
import charmhelpers.core.hookenv as hookenv

# This charm's library contains all of the handler code associated with
# sdn_charm
import charm.openstack.murano as murano  # noqa

charm.use_defaults(
    'charm.installed',
    'amqp.connected',
    'shared-db.connected',
    'identity-service.connected',
    'identity-service.available',  # enables SSL support
    'config.changed',
    'update-status')

COMPLETE_INTERFACE_STATES = [
    'shared-db.available',
    'identity-service.available',
    'amqp.available',
]

@reactive.when(*COMPLETE_INTERFACE_STATES)
def render_config(*args):
    """Render the configuration for charm when all the interfaces are
    available.
    """
    with charm.provide_charm_instance() as charm_class:
        charm_class.render_with_interfaces(args)
        charm_class.assess_status()
    murano.render_novarc_config(args)
    reactive.set_state('config.rendered')


# db_sync checks if sync has been done so rerunning is a noop
@reactive.when('config.rendered')
def init_db():
    with charm.provide_charm_instance() as charm_class:
        charm_class.db_sync()


@reactive.when_not('io-murano.imported')
@reactive.when(*COMPLETE_INTERFACE_STATES)
@reactive.when('config.rendered')
def import_io_murano(*args):
    murano.import_io_murano()
    reactive.set_state('io-murano.imported')


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    murano.configure_ha_resources(hacluster)
    murano.assess_status()


@reactive.hook('upgrade-charm')
def upgrade_charm():
    murano.install()
