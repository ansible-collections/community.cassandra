#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_assassinate
author: Rhys Campbell (@rhysmeister)
short_description: Run the assassinate command against a node.
requirements:
  - nodetool
description:
  - Run the assassinate command against a node.
  - Forcefully removes a dead node without re-replicating any data.
  - It is a last resort tool if you cannot successfully use nodetool removenode.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  ip_address:
    description:
      - IP Address of endpoint to assassinate.
    type: str
    required: yes
  debug:
    description:
      - Add additional debug output.
    type: bool
    default: false
'''

EXAMPLES = '''
- name: Assassinate a node
  community.cassandra.cassandra_assassinate:
    ip_address: 127.0.0.1
'''

RETURN = '''
msg:
  description: A short description of what happened.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        ip_address=dict(type='str', required=True),
        debug=dict(type='bool', default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    ip_address = module.params['ip_address']
    cmd = 'assassinate -- {0}'.format(ip_address)

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
        result['msg'] = "nodetool assassinate executed successfully for endpoint: {0}".format(ip_address)
        module.exit_json(**result)
    else:
        result['msg'] = "nodetool assassinate did not execute successfully rc: {0}".format(rc)
        module.fail_json(**result)


if __name__ == '__main__':
    main()
