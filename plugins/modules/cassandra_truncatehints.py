#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_truncatehints
author: Rhys Campbell (@rhysmeister)
short_description: Truncate all hints on the local node, or truncate hints for the endpoint(s) specified.
requirements:
  - nodetool
description:
  - Truncate all hints on the local node, or truncate hints for the endpoint(s) specified.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options
'''

EXAMPLES = '''
- name: Run truncatehints on the local node
  community.cassandra.cassandra_truncatehints:
'''

RETURN = '''
cassandra_flush:
  description: The return state of the executed command.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    argument_spec = cassandra_common_argument_spec()
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False)

    cmd = 'truncatehints'

    n = NodeToolCommandSimple(module, cmd)

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
        result['msg'] = "nodetool truncatehints executed successfully"
        module.exit_json(**result)
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool truncatehints did not execute successfully"
        module.exit_json(**result)


if __name__ == '__main__':
    main()
