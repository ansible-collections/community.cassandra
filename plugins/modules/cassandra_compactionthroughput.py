#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_compactionthroughput
author: Rhys Campbell (@rhysmeister)
short_description: Sets the compaction throughput.
requirements:
  - nodetool
description:
    - Sets the compaction throughput.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  value:
    description:
      - MB value to set compaction throughput to.
    type: int
    required: True
'''

EXAMPLES = '''
- name: Set compactionthroughput with module
  cassandra_compactionthroughput:
    value: 32
'''

RETURN = '''
community.cassandra.cassandra_compactionthroughput:
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
        value=dict(type='int', required=True)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    set_cmd = "setcompactionthroughput {0}".format(module.params['value'])
    get_cmd = "getcompactionthroughput"
    value = module.params['value']

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

    get_response = "Current compaction throughput: {0} MB/s".format(value)
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
