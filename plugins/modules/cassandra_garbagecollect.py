#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_garbagecollect
author: Rhys Campbell (@rhysmeister)
short_description: Removes deleted data from one or more tables.
requirements:
  - nodetool
description:
    - Removes deleted data from one or more tables.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  keyspace:
    description:
      - Keyspace to clean up data from.
    type: str
  table:
    description:
      - Table to clean up deleted data from.
    type: str
  granularity:
    description:
      - ROW (default) removes deleted partitions and rows.
      - CELL also removes overwritten or deleted cells.
    type: str
    default: "ROW"
    choices:
      - "ROW"
      - "CELL"
  jobs:
    description:
      - Number of SSTables affected simultaneously.
      - Set to 0 to use all compaction threads.
    type: int
    default: 2
'''

EXAMPLES = '''
- name: Remove deleted data from a table
  community.cassandra.cassandra_garbagecollect:
    keyspace: mykeyspace
    tables: mytable
'''

RETURN = '''
msg:
  description: A brief description of what happened.
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
        self.granularity = module.params['granularity']
        self.jobs = module.params['jobs']
        cmd = "{0} --granularity {1} --jobs {2}".format(cmd,
                                                        self.granularity,
                                                        self.jobs)
        if self.keyspace is not None:
            cmd = "{0} {1}".format(cmd, self.keyspace)
        if self.table is not None:
            cmd = "{0} {1}".format(cmd, self.table)

        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        keyspace=dict(type='str', no_log=False),
        table=dict(type='str'),
        granularity=dict(type='str', default="ROW", choices=["ROW", "CELL"]),
        jobs=dict(type='int', default=2)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    cmd = 'garbagecollect'

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
        result['msg'] = "nodetool garbagecollect executed successfully"
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool garbagecollect did not execute successfully"
    module.exit_json(**result)


if __name__ == '__main__':
    main()
