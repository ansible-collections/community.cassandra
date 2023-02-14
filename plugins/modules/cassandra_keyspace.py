#!/usr/bin/python

# Copyright: (c) 2019, Rhys Campbell <rhys.james.campbell@googlemail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = r'''
---
module: cassandra_keyspace
short_description: Manage keyspaces on your Cassandra cluster.
description:
   - Manage keyspaces on your Cassandra Cluster.
   - Keyspace can be created to use SimpleStrategy or NetworkTopologyStrategy.
   - "Keyspace modifications are supported, for example durable \
      writes, replication factor or data centre changes but it is not \
      supported to migrate between replication strategies \
      i.e. NetworkTopologyStrategy -> SimpleStrategy."
author: Rhys Campbell (@rhysmeister)
options:
  login_user:
    description: The Cassandra user to login with.
    type: str
  login_password:
    description: The Cassandra password to login with.
    type: str
  login_host:
    description:
      - The Cassandra hostname.
      - If unset the instance will check 127.0.0.1 for a C* instance.
      - Otherwise the value returned by socket.getfqdn() is used.
    type: list
    elements: str
  login_port:
    description: The Cassandra poret.
    type: int
    default: 9042
  name:
    description: The name of the keyspace to create or manage.
    type: str
    required: true
  state:
    description: The desired state of the keyspace.
    type: str
    choices:
      - "present"
      -  "absent"
    required: true
  replication_factor:
    description:
      - The total number of copies of your keyspace data.
      - The keyspace is created with SimpleStrategy.
      - If data_centres is set this parameter is ignored.
      - If not supplied the default value will be used.
    type: int
    default: 1
  durable_writes:
    description:
      - Enable durable writes for the keyspace.
      - If not supplied the default value will be used.
    type: bool
    default: true
  data_centres:
    description:
      - The keyspace will be created with NetworkTopologyStrategy.
      - Specify your data centres, along with replication_factor, as key-value pairs.
    type: dict

requirements:
  - cassandra-driver
'''

EXAMPLES = r'''
- name: Create a keyspace
  community.cassandra.cassandra_keyspace:
    name: mykeyspace
    state: present

- name: Remove a keyspace
  community.cassandra.cassandra_keyspace:
    name: mykeyspace
    state: absent

- name: Create a keyspace with RF 3
  community.cassandra.cassandra_keyspace:
    name: mykeyspace
    state: present
    replication_factor: 3

- name: Create a keyspace with network topology
  community.cassandra.cassandra_keyspace:
    name: mykeyspace
    data_centres:
      london: 3
      paris: 3
      tokyo: 1
      new_york: 1
'''


RETURN = '''
changed:
  description: Whether the module has changed the keyspace.
  returned: on success
  type: bool
cql:
  description: The cql used to change the keyspace.
  returned: changed
  type: str
  sample: "ALTER KEYSPACE multidc_keyspace WITH REPLICATION = { 'class' :/
   'NetworkTopologyStrategy', 'new_york' : 2,'tokyo' : 1,'zurich' : 3 } /
   AND DURABLE_WRITES = True"
keyspace:
  description: The keyspace operated on.
  returned: on success
  type: str
msg:
  description: Exceptions encountered during module execution.
  returned: on error
  type: str
'''

__metaclass__ = type
import re
import socket


try:
    from cassandra.cluster import Cluster, AuthenticationFailed
    from cassandra.auth import PlainTextAuthProvider
    HAS_CASSANDRA_DRIVER = True
except Exception:
    HAS_CASSANDRA_DRIVER = False

from ansible.module_utils.basic import AnsibleModule

# =========================================
# Cassandra module specific support methods
# =========================================


# Does the keyspace exists on the cluster? TODO Better to use cluster.metadata.keyspaces here?
def keyspace_exists(session, keyspace):
    server_version = session.execute("SELECT release_version FROM system.local WHERE key='local'")[0]
    if int(server_version.release_version[0]) >= 3:
        cql = "SELECT keyspace_name FROM system_schema.keyspaces"
    else:
        cql = "SELECT keyspace_name FROM system.schema_keyspaces"
    keyspaces = session.execute(cql)
    keyspace_exists = False
    for ks in keyspaces:
        if ks.keyspace_name == keyspace:
            keyspace_exists = True
    return keyspace_exists


def get_keyspace(cluster, keyspace):
    return cluster.metadata.keyspaces[keyspace].export_as_string()


def create_alter_keyspace(module, session, keyspace, replication_factor, durable_writes, data_centres, is_alter):
    if is_alter is False:
        cql = "CREATE KEYSPACE {0} ".format(keyspace)
    else:
        cql = "ALTER KEYSPACE {0} ".format(keyspace)
    if data_centres is not None:
        cql += "WITH REPLICATION = { 'class' : 'NetworkTopologyStrategy', "
        for dc in data_centres:
            cql += " '{0}' : {1},".format(str(dc), data_centres[dc])
        cql = cql[:-1] + " }"
    else:
        cql += "WITH REPLICATION = {{ 'class' : 'SimpleStrategy', 'replication_factor': {0} }}".format(replication_factor)
    cql += " AND DURABLE_WRITES = {0}".format(durable_writes)
    session.execute(cql)
    return cql


def drop_keyspace(session, keyspace):
    cql = "DROP KEYSPACE %s" % keyspace
    session.execute(cql)
    return True


def get_keyspace_config(module, cluster, keyspace):
    cql = get_keyspace(cluster, keyspace)
    dict_regexp = re.compile(r'{(.*)}')
    durable_writes_regexp = re.compile('DURABLE_WRITES = (True|False);')
    repl_settings = re.search(dict_regexp, cql).group(0)
    try:
        dw = re.search(durable_writes_regexp, cql).group(0)
    except AttributeError as excep:
        dw = "true"  # default to true
    keyspace_config = eval(repl_settings)
    keyspace_config['durable_writes'] = bool(dw.lower())
    return keyspace_config


def keyspace_is_changed(module, cluster, keyspace, replication_factor,
                        durable_writes, data_centres):
    cfg = get_keyspace_config(module, cluster, keyspace)
    keyspace_definition_changed = False
    if cfg['class'] == "SimpleStrategy":
        if int(cfg['replication_factor']) != replication_factor or\
                cfg['durable_writes'] != durable_writes:
            keyspace_definition_changed = True
    elif cfg['class'] == "NetworkTopologyStrategy":
        # ls = [cfg, keyspace, replication_factor, durable_writes, data_centres]
        # module.fail_json(msg=str(ls))
        if cfg['durable_writes'] != durable_writes:
            keyspace_definition_changed = True
        else:  # check each dc here
            for dc in data_centres:
                if dc in cfg.keys():
                    if int(data_centres[dc]) != int(cfg[dc]):
                        keyspace_definition_changed = True
                else:
                    keyspace_definition_changed = True
            # If still false check for removed dc's
            if keyspace_definition_changed is False:
                for dc in cfg.keys():
                    if dc not in data_centres and dc not in ["class", "durable_writes"]:
                        keyspace_definition_changed = True
    else:
        module.fail_json("Unknown Replication strategy: {0}".format(cfg['class']))
    return keyspace_definition_changed

############################################


def main():
    module = AnsibleModule(
        argument_spec=dict(
            login_user=dict(type='str'),
            login_password=dict(type='str', no_log=True),
            login_host=dict(type='list', elements='str', default=None),
            login_port=dict(type='int', default=9042),
            name=dict(type='str', required=True),
            state=dict(type='str', required=True, choices=['present', 'absent']),
            replication_factor=dict(type='int', default=1),
            durable_writes=dict(type='bool', default=True),
            data_centres=dict(type='dict')),
        supports_check_mode=True
    )

    if HAS_CASSANDRA_DRIVER is False:
        msg = ("This module requires the cassandra-driver python"
               " driver. You can probably install it with pip"
               " install cassandra-driver.")
        module.fail_json(msg=msg)

    login_user = module.params['login_user']
    login_password = module.params['login_password']
    login_host = module.params['login_host']
    login_port = module.params['login_port']
    if login_host is None:
        login_host = []
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex(('127.0.0.1', login_port))
        if result == 0:
            login_host.append('127.0.0.1')
        else:
            login_host.append(socket.getfqdn())

    name = module.params['name']
    keyspace = name
    state = module.params['state']
    replication_factor = module.params['replication_factor']
    durable_writes = module.params['durable_writes']
    data_centres = module.params['data_centres']

    result = dict(
        changed=False,
        keyspace=name,
    )

    # For now we won't change the replication strategy & options if the keyspace already exists
    # If and when we do we might only support updating the options rather than the replication class itself

    try:
        auth_provider = None
        if login_user is not None:
            auth_provider = PlainTextAuthProvider(
                username=login_user,
                password=login_password
            )
        cluster = Cluster(login_host,
                          port=login_port,
                          auth_provider=auth_provider)
        session = cluster.connect()
    except AuthenticationFailed as excep:
        module.fail_json(msg="Authentication failed: {0}".format(excep))
    except Exception as excep:
        module.fail_json(msg="Error connecting to cluster: {0}".format(excep))

    try:
        if keyspace_exists(session, keyspace):
            if module.check_mode:
                if state == "present":
                    if keyspace_is_changed(module,
                                           cluster,
                                           keyspace,
                                           replication_factor,
                                           durable_writes,
                                           data_centres):

                        result['changed'] = True
                    else:
                        result['changed'] = False
                elif state == "absent":
                    result['changed'] = True
            else:
                if state == "present":
                    if keyspace_is_changed(module,
                                           cluster,
                                           keyspace,
                                           replication_factor,
                                           durable_writes,
                                           data_centres):

                        cql = create_alter_keyspace(module,
                                                    session,
                                                    keyspace,
                                                    replication_factor,
                                                    durable_writes,
                                                    data_centres,
                                                    True)
                        result['changed'] = True
                        result['cql'] = cql
                    else:
                        result['changed'] = False
                elif state == "absent":
                    drop_keyspace(session, keyspace)
                    result['changed'] = True
        else:
            if module.check_mode:
                if state == "present":
                    result['changed'] = True
                if state == "absent":
                    result['changed'] = False
            else:
                if state == "present":
                    cql = create_alter_keyspace(module,
                                                session,
                                                keyspace,
                                                replication_factor,
                                                durable_writes,
                                                data_centres,
                                                False)
                    result['changed'] = True
                    result['cql'] = cql
                elif state == "absent":
                    result['changed'] = False

        module.exit_json(**result)

    except Exception as excep:
        module.fail_json(msg="An error occured: {0}".format(excep))


if __name__ == '__main__':
    main()
