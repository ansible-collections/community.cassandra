#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_compactionthreshold
author: Rhys Campbell (@rhysmeister)
short_description: Sets the compaction threshold.
requirements:
  - nodetool
description:
    - Sets the compaction threshold.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  keyspace:
    description:
      - The keyspace to adjust compaction thresholds for.
    type: str
    required: True
  table:
    description:
      - The table to adjust compaction thresholds for.
    type: str
    required: True
  min:
    description: >
      Sets the minimum number of SSTables to trigger a minor compaction when
      using SizeTieredCompactionStrategy or DateTieredCompactionStrategy.
    type: int
    required: True
  max:
    description: >
      Sets the maximum number of SSTables to allow in a minor compaction when
      using SizeTieredCompactionStrategy or DateTieredCompactionStrategy.
    type: int
    required: True
'''

EXAMPLES = '''
- name: Adjust compactionthreshold with module
  community.cassandra.cassandra_compactionthreshold:
    keyspace: system
    table: local
    min: 8
    max: 64
'''

RETURN = '''
cassandra_compactionthreshold:
  description: The return state of the executed command.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolGetSetCommand
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        keyspace=dict(type='str', required=True, no_log=False),
        table=dict(type='str', required=True),
        min=dict(type='int', required=True),
        max=dict(type='int', required=True)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    keyspace = module.params['keyspace']
    table = module.params['table']
    min = module.params['min']
    max = module.params['max']
    set_cmd = "setcompactionthreshold {0} {1} {2} {3}".format(keyspace,
                                                              table,
                                                              min,
                                                              max)
    get_cmd = "getcompactionthreshold {0} {1}".format(keyspace, table)

    n = NodeToolGetSetCommand(module, get_cmd, set_cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.get_command()
    out = out.strip()

    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

    get_response = "Current compaction thresholds for {0}/{1}: \n min = {2},  max = {3}".format(keyspace, table, min, max)
    if get_response == out:

        if rc != 0:
            result['changed'] = False
            module.fail_json(name=get_cmd,
                             msg="get command failed", **result)
    else:

        if module.check_mode:
            result['changed'] = True
        else:
            (rc, out, err) = n.set_command()
            out = out.strip()
            if module.params['debug']:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
            if rc != 0:
                result['changed'] = False
                module.fail_json(name=set_cmd,
                                 msg="set command failed", **result)
            else:
                result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
