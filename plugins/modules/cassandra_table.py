#!/usr/bin/python

# Copyright: (c) 2019, Rhys Campbell <rhys.james.campbell@googlemail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = r'''
---
module: cassandra_table
short_description: Create or drop tables on a Cassandra Keyspace.
description:
   - Create or drop tables on a Cassandra Keyspace.
   - No alter functionality. If a table with the same name already exists then no changes are made.
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
    type: list
    elements: str
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
    choices:
      - "present"
      - "absent"
    required: true
  keyspace:
    description:
      - The keyspace in which to create the table.
    type: str
    required: true
  columns:
    description:
      - The columns for the table.
      - "Specifiy pairs as <column name>: <data type>"
    type: list
    elements: dict
  primary_key:
    description:
      - The Primary key speicfication for the table
    type: list
    elements: str
  partition_key:
    description:
      - The partition key columns.
    type: list
    elements: str
    required: false
    default: []
  clustering:
    description:
      - The clustering specification.
    type: list
    elements: dict
  table_options:
    description:
      - Options for the table
    type: dict
  is_type:
    description:
      - Create a type instead of a table
    type: bool
    default: False
  debug:
    description:
      - Debug flag
    type: bool
    default: false
'''

EXAMPLES = r'''
- name: Create a table
  community.cassandra.cassandra_table:
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
  community.cassandra.cassandra_table:
    name: users
    state: absent
    keyspace: myapp

# killrvideo examples
- name: Create user_credentials table
  community.cassandra.cassandra_table:
    name: user_credentials
    state: present
    keyspace: killrvideo
    columns:
      - email: text
      - password: text
      - userid: uuid
    primary_key:
      - email
    login_user: admin
    login_password: secret
  register: user_credentials

- name: Create user table
  community.cassandra.cassandra_table:
    name: users
    state: present
    keyspace: killrvideo
    columns:
      - userid: uuid
      - firstname: varchar
      - lastname: varchar
      - email: text
      - created_date: timestamp
    primary_key:
      - userid
    login_user: admin
    login_password: secret
  register: users

- name: Create video_metadata type
  community.cassandra.cassandra_table:
    name: video_metadata
    state: present
    keyspace: killrvideo
    columns:
      - height: int
      - width: int
      - video_bit_rate: "set<text>"
      - encoding: text
    is_type: True
    login_user: admin
    login_password: secret
  register: video_metadata

- name: Create videos table
  community.cassandra.cassandra_table:
    name: videos
    state: present
    keyspace: killrvideo
    columns:
      - videoid: uuid
      - userid: uuid
      - name: varchar
      - description: varchar
      - location: text
      - location_type: int
      - preview_thumbnails: "map<text,text>"
      - tags: "set<varchar>"
      - metadata: "set<frozen<video_metadata>>"
      - added_date: "timestamp"
    primary_key:
      - videoid
    login_user: admin
    login_password: secret
  register: videos

- name: Create user_videos table
  community.cassandra.cassandra_table:
    name: user_videos
    state: present
    keyspace: killrvideo
    columns:
      - userid: uuid
      - added_date: timestamp
      - videoid: uuid
      - name: text
      - preview_image_location: text
    primary_key:
      - userid
      - added_date
      - videoid
    clustering:
      - added_date: "DESC"
      - videoid: "ASC"
    login_user: admin
    login_password: secret
  register: user_videos

- name: Create latest_videos table
  community.cassandra.cassandra_table:
    name: latest_videos
    state: present
    keyspace: killrvideo
    columns:
      - yyyymmdd: text
      - added_date: timestamp
      - videoid: uuid
      - name: text
      - preview_image_location: text
    primary_key:
      - yyyymmdd
      - added_date
      - videoid
    clustering:
      - added_date: "DESC"
      - videoid: "ASC"
    login_user: admin
    login_password: secret
  register: latest_videos
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

__metaclass__ = type


try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
    from cassandra import AuthenticationFailed
    HAS_CASSANDRA_DRIVER = True
except Exception:
    HAS_CASSANDRA_DRIVER = False

from ansible.module_utils.basic import AnsibleModule

# =========================================
# Cassandra module specific support methods
# =========================================


# Does the table exist on the cluster?
def table_exists(session,
                 keyspace_name,
                 table_name):
    server_version = session.execute("SELECT release_version FROM system.local WHERE key='local'")[0]
    if int(server_version.release_version[0]) >= 3:
        cql = "SELECT table_name FROM system_schema.tables WHERE keyspace_name = '{0}' AND table_name = '{1}'".format(keyspace_name,
                                                                                                                      table_name)
    else:
        cql = "SELECT columnfamily_name AS table_name \
                FROM system.schema_columnfamilies \
                WHERE keyspace_name = '{0}' \
                AND columnfamily_name = '{1}';".format(keyspace_name, table_name)
    t = session.execute(cql)
    s = False
    if len(list(t)) > 0:
        s = True
    return s


def findnth(haystack, needle, n):
    '''
    Helper function used in create_primary_key_with_partition_key
    '''
    parts = haystack.split(needle, n + 1)
    if len(parts) <= n + 1:
        return -1
    return len(haystack) - len(parts[-1]) - len(needle)


def create_primary_key_with_partition_key(primary_key, partition_key):
    '''
    We return the correct cql for the primary key with
    the partiton key when appropriate
    '''
    p_key_count = len(partition_key)
    for i, val in enumerate(partition_key):
        if not val == primary_key[i]:
            raise ValueError("partition_key list elements do not match primary_key elements")
    pk_cql = "PRIMARY KEY ({0}))".format(", ".join(primary_key))
    if p_key_count > 0:  # Need to insert the brackets for pk
        pos = findnth(pk_cql, ",", p_key_count - 1)
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
        cql += "{0} {1}, ".format(list(column.keys())[0], list(column.values())[0])
    # cql += "PRIMARY KEY ({0}))".format(str(primary_key.keys()).replace('[', '').replace(']', '').replace("'", '')) # TODO Partition
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
            cql += "{0} {1}, ".format(list(c.keys())[0], list(c.values())[0])
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

    # required_if_args = [
    #    ["state", "present", ["columns", "primary_key"]]
    # ]

    module = AnsibleModule(
        argument_spec=dict(
            login_user=dict(type='str'),
            login_password=dict(type='str', no_log=True),
            login_host=dict(type='list', elements='str'),
            login_port=dict(type='int', default=9042),
            name=dict(type='str', required=True),
            state=dict(type='str', required=True, choices=['present', 'absent']),
            keyspace=dict(type='str', required=True, no_log=False),
            columns=dict(type='list', elements='dict'),
            primary_key=dict(type='list', elements='str', no_log=False),
            clustering=dict(type='list', elements='dict'),
            partition_key=dict(type='list', elements='str', default=[], no_log=False),
            table_options=dict(type='dict', default=None),
            is_type=dict(type='bool', default=False),
            debug=dict(type='bool', default=False)),
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

    if is_type is False and state == "present":
        if columns is None or primary_key is None:
            module.fail_json(msg="Both columns and primary_key must be specified when creating a table")

    result = dict(
        changed=False,
        cql=None,
    )

    cql = None

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
        if table_exists(session, keyspace_name, table_name):
            if state == "present":
                result['changed'] = False
            else:
                cql = drop_table(keyspace_name, table_name)
                if not module.check_mode:
                    session.execute(cql)
                result['changed'] = True
                result['cql'] = cql
        else:  # Table does not exist
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
        msg = str(excep)
        if cql is not None:
            msg += " | {0}".format(cql)
        if debug:
            module.fail_json(msg=msg, **result)
        else:
            module.fail_json(msg=msg, **result)


if __name__ == '__main__':
    main()
