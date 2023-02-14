#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_decommission
author: Rhys Campbell (@rhysmeister)
short_description: Deactivates a node by streaming its data to another node.
requirements:
  - nodetool
description:
    - Deactivates a node by streaming its data to another node.
    - Uses the nodetool ring command to determine if the node is still in the cluster.
    - To ensure correct function of this module please use the ip address of the node in the host parameter.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  debug:
    description:
      - Add additional debug to module output.
    type: bool
    default: False
'''

EXAMPLES = '''
- name: Decommission a node
  community.cassandra.cassandra_decommission:
'''

RETURN = '''
msg:
  description: A message indicating what has happened.
  returned: on failure
  type: bool
rc:
  description: Return code of the executed command.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        debug=dict(type='bool', default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    debug = module.params['debug']

    result = {}

    cmd = "ring"

    rc = None
    out = ''
    err = ''
    result = {}

    n = NodeToolCommandSimple(module, cmd)

    (rc, out, err) = n.run_command()
    out = out.strip()
    err = err.strip()
    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

    if rc == 0:
        if module.params['host'] in out:  # host is still in ring
            cmd = "decommission"
            n = NodeToolCommandSimple(module, cmd)
            if not module.check_mode:
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
                    result['msg'] = "decommission command succeeded"
                else:
                    result['msg'] = "decommission command failed"
                    result['rc'] = rc
                    module.fail_json(**result)
            else:
                result['changed'] = True
                result['msg'] = "decommission command succeeded"
        else:
            result['changed'] = False
            result['msg'] = "Node appears to be already decommissioned"
        module.exit_json(**result)
    else:
        result['msg'] = "decommission command failed"
        result['rc'] = rc
        module.fail_json(**result)

    # Everything is good
    module.exit_json(**result)


if __name__ == '__main__':
    main()
