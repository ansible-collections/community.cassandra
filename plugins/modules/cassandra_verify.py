#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_verify
author: Rhys Campbell (@rhysmeister)
short_description: Checks the data checksum for one or more tables.
requirements:
  - nodetool
description:
    - Checks the data checksum for one or more tables.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  keyspace:
    description:
      - Optional keyspace.
    type: str
  table:
    description:
      - Optional table name or list of table names.
    type: raw
  extended:
    description:
      - Extended verify.
      - Each cell data, beyond simply checking SSTable checksums.
    type: bool
    default: False
    aliases:
      - e
'''

EXAMPLES = '''
- name: Run verify on the Cassandra node
  community.cassandra.cassandra_verify:
    keyspace: mykeyspace
    tables:
      - table1
      - table2
'''

RETURN = '''
cassandra_verify:
  description: The return state of the executed command.
  returned: success
  type: str
'''


from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCmd
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


class NodeToolCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;
        - run_command
    2020.01.10 - Added additonal keyspace and table params
    """

    def __init__(self, module, cmd):
        NodeToolCmd.__init__(self, module)
        self.keyspace = module.params['keyspace']
        self.table = module.params['table']
        self.extended = module.params['extended']
        if self.extended:
            cmd = "{0} -e".format(cmd)
        if self.keyspace is not None:
            cmd = "{0} {1}".format(cmd, self.keyspace)
        if self.table is not None:
            if isinstance(self.table, str):
                cmd = "{0} {1}".format(cmd, self.table)
            elif isinstance(self.table, list):
                cmd = "{0} {1}".format(cmd, " ".join(self.table))
        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        keyspace=dict(type='str', default=None, required=False, no_log=False),
        table=dict(type='raw', default=None, required=False),
        extended=dict(type='bool', default=False, required=False, aliases=['e'])
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    cmd = 'verify'

    n = NodeToolCommand(module, cmd)

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
        result['msg'] = "nodetool verify executed successfully"
        module.exit_json(**result)
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool verify did not execute successfully"
        module.exit_json(**result)


if __name__ == '__main__':
    main()
