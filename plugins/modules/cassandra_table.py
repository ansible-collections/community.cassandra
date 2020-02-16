#!/usr/bin/python

# Copyright: (c) 2019, Rhys Campbell <rhys.james.campbell@googlemail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type
import re
import sys
import traceback
import collections

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: cassandra_table
short_description: Create or drop tables on a Cassandra database.
description:
   - Create or drop tables on a Cassandra database.
   - No alter functionality.
 version_added: 2.9
 author: Rhys Campbell (@rhysmeister)
 options:
   login_user:
     description: The Cassandra user to login with.
     type: str
   login_password:
     description: The Cassandra password to login with.
     type: str
   login_host:
     description: The Cassandra hostname.
     type: str
   login_port:
     description: The Cassandra poret.
     type: int
     default: 9042
   name:
     description: The name of the table to create or drop.
     type: str
     required: true
   state:
     description: The desired state of the table.
     type: str
     choices: [ "present", "absent" ]
     required: true
   keyspace:
     description:
       - The keyspace in which to create the table.
      type: boolean
      required: true
      default: false
   columns:
     description:
       - The columns for the table.
       - Specifiy dict as <column name>: <data type>
     type: dict
     required: false
   primary_key:
     description:
       - The Primary key speicfication for the table
       - TODO - How to specify the partition key?
     type: list
     required: true
   clustering:
     description:
       - The clustering specification.
     type: list
   table_options:
     description:
       - Options for the table
     type: dict
   is_type:
     description:
       - Create a type instead of a table
     type: bool
'''

EXAMPLES = r'''
- name: Create a table
  cassandra_table:
    name: users
    state: present
    keyspace: myapp
    columns:
      id: UUID
      username: text
      encrypted_password: blob
      email: text
      dob: date
      first_name: text
      last_name: text
      points: int
    primary_key:
      username

- name: Remove a table
  cassandra_table:
    name: users
    state: absent
    keyspace: myapp
'''


RETURN = '''
changed:
  description: Whether the module has created or dropped
  returned: on success
  type: bool
cql:
  description: The cql used to create or drop the table
  returned: changed
  type: str
  sample: "DROP TABLE users"
msg:
  description: Exceptions encountered during module execution.
  returned: on error
  type: str
'''

try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
    from cassandra import AuthenticationFailed
    from cassandra.query import dict_factory
    from cassandra import InvalidRequest
    HAS_CASSANDRA_DRIVER = True
except:
    HAS_CASSANDRA_DRIVER = False

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import binary_type, text_type
from ansible.module_utils.six.moves import configparser
from ansible.module_utils._text import to_native

# =========================================
# Cassandra module specific support methods
# =========================================

# Does the role exist on the cluster?
def table_exists(session,
                 keyspace_name,
                 table_name):
    cql = "SELECT table_name FROM system_schema.tables WHERE keyspace_name = '{0}' AND table_name = '{1}'".format(keyspace_name,
                                                                                                                  table_name)
    t = session.execute(cql)
    s = False
    if len(list(t)) > 0:
        s = True
    return s


def findnth(haystack, needle, n):
    '''
    Helper function used in create_primary_key_with_partition_key
    '''
    parts= haystack.split(needle, n+1)
    if len(parts)<=n+1:
        return -1
    return len(haystack)-len(parts[-1])-len(needle)


def create_primary_key_with_partition_key(primary_key, partition_key):
    '''
    We return the correct cql for the primary key with
    the partiton key when appropriate
    '''
    p_key_count = len(partition_key)
    for i, val in enumerate(partition_key):
        if not partition_key[i] == primary_key[i]:
            raise ValueException("partition_key list elements do not match primary_key elements")
    pk_cql = "PRIMARY KEY ({0}))".format(", ".join(primary_key))
    if p_key_count > 0: # Need to insert the brackets for pk
        pos = findnth(pk_cql, ",", p_key_count -1)
        pk_cql = pk_cql[:13] + "(" + pk_cql[13:pos] + ")" + pk_cql[pos:]
    return pk_cql


def create_table(keyspace_name,
                 table_name,
                 columns,
                 primary_key,
                 clustering,
                 partition_key,
                 table_options,
                 is_type):
    used_with = False
    word = "TABLE"
    if is_type:
        word = "TYPE"
    cql = "CREATE {0} {1}.{2}".format(word,
                                      keyspace_name,
                                      table_name)
    cql += " ( "
    for column in columns:
        cql += "{0} {1}, ".format(column.keys()[0], column.values()[0])
    #cql += "PRIMARY KEY ({0}))".format(str(primary_key.keys()).replace('[', '').replace(']', '').replace("'", '')) # TODO Partition
    if primary_key is not None:
        pk_cql = create_primary_key_with_partition_key(primary_key,
                                                       partition_key)
        cql += pk_cql
    else:
        cql += ")"
    if clustering is not None:
        cql += " WITH CLUSTERING ORDER BY ("
        used_with = True
        for c in clustering:
            cql += "{0} {1}, ".format(c.keys()[0], c.values()[0])
        cql = cql[:-2] + ")"
    if table_options is not None:
        for option in table_options:
            word = "AND"
            if not used_with:
                word = "WITH"
                used_with = True
            cql += " {0} {1} = {2}".format(word,
                                           option,
                                           table_options[option])
    return cql


def drop_table(keyspace_name,
               table_name):
    cql = "DROP TABLE {0}.{1}".format(keyspace_name,
                                      table_name)
    return cql




############################################

def main():
    module = AnsibleModule(
        argument_spec=dict(
            login_user=dict(type='str'),
            login_password=dict(type='str', no_log=True),
            login_host=dict(type='list', default="localhost"),
            login_port=dict(type='int', default=9042),
            name=dict(type='str', required=True),
            state=dict(type='str', required=True, choices=['present', 'absent']),
            keyspace=dict(type='str', required=True),
            columns=dict(type='list', default=None),
            primary_key=dict(type='list', default=None),
            clustering=dict(type='list', default=None),
            partition_key=dict(type='list', default=[]),
            table_options=dict(type='dict', default=None),
            is_type=dict(type='bool', default=False),
            debug=dict(type='bool', default=False)),
    supports_check_mode=True
    )

    if not HAS_CASSANDRA_DRIVER:
        module.fail_json(msg="This module requires the cassandra-driver python driver. You can probably install it with pip install cassandra-driver.")

    required_if=[
      [ "state", "present", [ "columns", "primary_key" ] ]
    ]

    login_user = module.params['login_user']
    login_password = module.params['login_password']
    login_host = module.params['login_host']
    login_port = module.params['login_port']
    table_name = module.params['name']
    state = module.params['state']
    keyspace_name = module.params['keyspace']
    columns = module.params['columns']
    primary_key = module.params['primary_key']
    clustering = module.params['clustering']
    partition_key = module.params['partition_key']
    table_options = module.params['table_options']
    is_type = module.params['is_type']
    debug = module.params['debug']

    result = dict(
        changed=False,
        cql=None,
    )

    cql = None


    try:
        auth_provider = None
        if login_user is not None:
            auth_provider = PlainTextAuthProvider(
                username = login_user,
                password = login_password
            )
        cluster = Cluster(login_host,
                          port=login_port,
                          auth_provider=auth_provider)
        session = cluster.connect()
    except AuthenticationFailed as auth_failed:
        module.fail_json(msg="Authentication failed: {0}".format(excep))
    except Exception as excep:
        module.fail_json(msg="Error connecting to cluster: {0}".format(excep))

    try:
        if table_exists(session, keyspace_name, table_name):
            if state == "present":
                result['changed'] = False
            else:
                cql = drop_table(keyspace_name, table_name)
                if not module.check_mode:
                    session.execute(cql)
                result['changed'] = True
                result['cql'] = cql
        else: # Table does not exist
                if state == "present":
                    cql = create_table(keyspace_name,
                                       table_name,
                                       columns,
                                       primary_key,
                                       clustering,
                                       partition_key,
                                       table_options,
                                       is_type)
                    if not module.check_mode:
                        session.execute(cql)
                    result['changed'] = True
                    result['cql'] = cql
                else:
                    result['changed'] = False

        module.exit_json(**result)

    except Exception as excep:
        exType, ex, tb = sys.exc_info()
        msg = "An error occured on line {0}: {1} | {2} | {3} | {4}".format(traceback.tb_lineno(tb),
                                                                     excep,
                                                                     exType,
                                                                     ex,
                                                                     traceback.print_exc())
        if cql is not None:
            msg+= " | {0}".format(cql)
        if debug:
            module.fail_json(msg=msg, **result)
        else:
            module.fail_json(msg=msg, **result)


if __name__ == '__main__':
    main()
