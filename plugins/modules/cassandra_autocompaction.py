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
short_description: Enabled or disables autocompaction.
requirements: [ nodetool ]
description:
    - Enabled or disables autocompaction.
options:
  host:
    description:
      - The hostname.
    type: str
    default: 127.0.0.1
  port:
    description:
      - The Cassandra TCP port.
    type: int
    default: 7199
  password:
    description:
      - The password to authenticate with.
    type: str
  password_file:
    description:
      - Path to a file containing the password.
    type: str
  username:
    description:
      - The username to authenticate with.
    type: str
  keyspace:
    description:
      - The keyspace to operate on.
    type: str
    required: true
  table:
    description:
      - The table to operate on.
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
  nodetool_path:
    description:
      - The path to nodetool.
    type: str
  debug:
    description:
      - Enable additional debug output.
    type: bool
'''

EXAMPLES = '''
- name: Ensure Cassandra Autocompaction is enabled
  cassandra_autocompaction:
    keyspace: system
    table: local
    state: enabled

- name: Ensure Cassandra Autocompaction is disabled
  cassandra_autocompaction:
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

from ansible.module_utils.basic import AnsibleModule, load_platform_subclass
__metaclass__ = type
import socket


from ansible_collections.community.cassandra.plugins.module_utils.NodeToolCmdObjects import NodeToolCmd, NodeTool2PairCommand


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', default="127.0.0.1"),
            port=dict(type='int', default=7199),
            password=dict(type='str', no_log=True),
            password_file=dict(type='str', no_log=True),
            username=dict(type='str', no_log=True),
            keyspace=dict(type='str', required=True),
            table=dict(type='list', elements='str', required=True),
            state=dict(required=True, choices=['enabled', 'disabled']),
            nodetool_path=dict(type='str', default=None, required=False),
            debug=dict(type='bool', default=False, required=False),
        ),
        supports_check_mode=False
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

        if module.debug:
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

        if module.debug:
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
