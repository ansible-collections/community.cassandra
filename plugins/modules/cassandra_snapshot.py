#!/usr/bin/python

# 2024 Jaymit Patel <18jaymit@gmail.com>
# https://github.com/jaymitp
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_snapshot
author: Jaymit Patel (@jaymitp)
short_description: Take a snapshot of one or more keyspaces, or tables to backup data.
requirements:
  - nodetool
description:
    - Used to back up data using a snapshot.
    - Take snapshots of keyspaces or tables.
    - Optionally skip flushing the node before taking a snapshot

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  keyspace:
    description:
      - "Optional keyspace to snapshot. Default: all keyspaces."
    type: list
    elements: str
  table:
    description:
      - Optional table to snapshot. You must specify one and only one keyspace.
    type: raw
  keyspace_table:
    description:
      - Optional keyspace.table to snapshot.
    type: list
    elements: str
  name:
    description:
      - Name of the snapshot.
    type: str
    aliases:
      - tag
      - t
  skip_flush:
    description:
      - Executes the snapshot without flushing the tables first
    type: bool
    aliases:
      - sf
    default: False
'''

EXAMPLES = '''
- name: Snapshot all keyspaces on the node
  community.cassandra.cassandra_snapshot:

- name: Snapshot multiple keyspaces on the node without flushing node
  community.cassandra.cassandra_snapshot:
    keyspace: keyspace1, keyspace2
    skip_flush: true

- name: Snapshot single keyspace with snapshot name 01-01-2024
  community.cassandra.cassandra_snapshot:
    keyspace: mykeyspace
    name: 01-01-2024

- name: Snapshot single table in a keyspace
  community.cassandra.cassandra_snapshot:
    keyspace: mykeyspace
    table: mytable

- name: Snapshot several tables in the same/different keyspaces
  community.cassandra.cassandra_snapshot:
    keyspace_table: mykeyspace.table, mykeyspace.table2, test.table1
    name: test_backup
'''

RETURN = '''
snapshot_dir:
  description: Name of a snapshot directory.
  returned: on success
  type: str
msg:
  description: A message indicating what has happened.
  returned: on success
  type: str
rc:
  description: Return code of the last executed command.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCmd
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


class NodeToolSnapshotCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;
        - run_command
    """
    def __init__(self, module, cmd):
        NodeToolCmd.__init__(self, module)
        self.keyspace = module.params["keyspace"]
        self.table = module.params["table"]
        self.keyspace_table = module.params["keyspace_table"]
        self.skip_flush = module.params["skip_flush"]
        self.name = module.params["name"]

        if self.skip_flush:
            cmd = "{0} -sf".format(cmd)
        if self.name is not None:
            cmd = "{0} -t {1}".format(cmd, self.name)
        if self.table is not None:
            cmd = "{0} -cf {1}".format(cmd, self.table)
        if self.keyspace_table is not None:
            if isinstance(self.keyspace_table, str):
                cmd = "{0} -kt {1}".format(cmd, self.keyspace_table)
            elif isinstance(self.keyspace_table, list):
                cmd = "{0} -kt {1}".format(cmd, (",".join(self.keyspace_table)).replace(" ", ""))
        if self.keyspace is not None:
            cmd = "{0} {1}".format(cmd, " ".join(self.keyspace))
        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        keyspace=dict(type='list', elements='str', default=None, required=False, no_log=False),
        table=dict(type='raw', default=None, required=False),
        keyspace_table=dict(type='list', elements='str', default=None, required=False, no_log=False),
        skip_flush=dict(type='bool', default=False, aliases=['sf'], required=False),
        name=dict(type='str', default=None, aliases=['tag', 't'], required=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,     # Maybe, will need to make use of listsnapshots though
    )

    cmd = "snapshot"

    n = NodeToolSnapshotCommand(module, cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.run_command()
    out = out.strip()
    err = err.strip()
    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

    if rc == 0:
        result['changed'] = True
        result['msg'] = "nodetool snapshot executed successfully"
        result['snapshot_dir'] = out.split(" ")[-1]
        module.exit_json(**result)
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool snapshot did not execute successfully"
        module.exit_json(**result)


if __name__ == '__main__':
    main()
