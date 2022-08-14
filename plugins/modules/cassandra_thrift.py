#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_thrift
author: Rhys Campbell (@rhysmeister)
short_description: Enables or disables the Thrift server.
requirements: [ nodetool ]
description:
    Enables or disables the Thrift server.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  state:
    description:
      - The required status
    type: str
    choices:
      - "enabled"
      - "disabled"
    required: true
'''

EXAMPLES = '''
- name: Ensure Cassandra thrift is enabled
  community.cassandra.cassandra_thrift:
    state: enabled

- name: Ensure Cassandra thrift is disabled
  community.cassandra.cassandra_thrift:
    state: disabled
'''

RETURN = '''
cassandra_gossip:
  description: The return state of the executed command.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeTool3PairCommand
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        state=dict(required=True, choices=['enabled', 'disabled'])
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    status_cmd = 'statusthrift'
    enable_cmd = 'enablethrift'
    disable_cmd = 'disablethrift'
    status_active = 'running'
    status_inactive = 'not running'

    n = NodeTool3PairCommand(module, status_cmd, enable_cmd, disable_cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.status_command()
    out = out.strip()
    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

    if module.params['state'] == "disabled":

        if rc != 0:
            module.fail_json(name=status_cmd,
                             msg="status command failed", **result)
        if module.check_mode:
            if out == status_active:
                module.exit_json(changed=True, msg=status_inactive, **result)
            else:
                module.exit_json(changed=False, msg=status_active, **result)
        if out == status_active:
            (rc, out, err) = n.disable_command()
        if module.params['debug']:
            if out:
                result['stdout'] = out
            if err:
                result['stderr'] = err
        if rc != 0:
            module.fail_json(name=disable_cmd,
                             msg="disable command failed", **result)
        else:
            result['msg'] = status_inactive
            result['changed'] = True

    elif module.params['state'] == "enabled":

        if rc != 0:
            module.fail_json(name=status_cmd,
                             msg="status command failed", **result)
        if module.check_mode:
            if out == status_inactive:
                module.exit_json(changed=True, msg=status_active, **result)
            else:
                module.exit_json(changed=False, msg=status_inactive, **result)
        if out == status_inactive:
            (rc, out, err) = n.enable_command()
            if module.params['debug']:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
        if rc is not None and rc != 0:
            module.fail_json(name=enable_cmd,
                             msg="enable command failed", **result)
        else:
            result['msg'] = status_active
            result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
