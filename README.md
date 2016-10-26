# Overview

Murano charm provides a catalog of applications deployable on Openstack cloud.

# Usage

Murano relies on services from the mysql/percona, rabbitmq-server and keystone charms:

    juju deploy murano
    juju deploy keystone
    juju deploy mysql
    juju deploy rabbitmq-server
    juju add-relation murano rabbitmq-server
    juju add-relation murano mysql
    juju add-relation murano keystone


# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-murano/+filebug).

For general questions please refer to the OpenStack [Charm Guide](https://github.com/openstack/charm-guide).
