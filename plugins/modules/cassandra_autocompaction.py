#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_autocompaction
author: Rhys Campbell (@rhysmeister)
short_description: Enables or disables autocompaction.
requirements: [ nodetool ]
description:
    - Enables or disables autocompaction.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  keyspace:
    description:
      - The keyspace on which to change autocompact status.
    type: str
    required: true
  table:
    description:
      - The table on which to change autocompact status.
    type: list
    elements: str
    required: true
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
- name: Ensure Cassandra Autocompaction is enabled
  community.cassandra.cassandra_autocompaction:
    keyspace: system
    table: local
    state: enabled

- name: Ensure Cassandra Autocompaction is disabled
  community.cassandra.cassandra_autocompaction:
    keyspace: system
    table: local
    state: disabled
'''

RETURN = '''
cassandra_autocompaction:
  description: The return state of the executed command.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeTool2PairCommand
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        keyspace=dict(type='str', required=True, no_log=False),
        table=dict(type='list', elements='str', required=True),
        state=dict(required=True, choices=['enabled', 'disabled'])
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    keyspace = module.params['keyspace']
    table = ' '.join(module.params['table'])
    enable_cmd = 'enableautocompaction {0} {1}'.format(keyspace, table)
    disable_cmd = 'disableautocompaction {0} {1}'.format(keyspace, table)

    n = NodeTool2PairCommand(module, enable_cmd, disable_cmd)

    rc = None
    out = ''
    err = ''
    result = {}
    result['changed'] = False

    # We don't know if this has changed or not
    if module.params['state'] == "enabled":

        (rc, out, err) = n.enable_command()
        out = out.strip()

        if module.params['debug']:
            if out:
                result['stdout'] = out
            if err:
                result['stderr'] = err

        if rc != 0:
            result['msg'] = "enable command failed"
            module.fail_json(name=enable_cmd,
                             **result)
        else:
            result['changed'] = True

    elif module.params['state'] == "disabled":

        (rc, out, err) = n.disable_command()
        out = out.strip()

        if module.params['debug']:
            if out:
                result['stdout'] = out
            if err:
                result['stderr'] = err

        if rc != 0:
            result['msg'] = "disable command failed"
            module.fail_json(name=disable_cmd,
                             **result)
        else:
            result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
