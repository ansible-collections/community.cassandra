#!/usr/bin/python

# 2026 Alain Rodriguez <alain@casterix.fr>
# https://github.com/arodrime
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_statusbinary
author: Alain Rodriguez (@arodrime)
short_description: Returns the status of the binary protocol.
requirements:
  - nodetool
description:
    - Returns the status of the binary protocol, also known as the native transport.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options
'''

EXAMPLES = '''
- name: Get binary protocol status
  community.cassandra.cassandra_statusbinary:
  register: result

- name: Assert binary is running
  assert:
    that: result.is_up
'''

RETURN = '''
is_up:
  description: True if the binary protocol is running, False otherwise.
  returned: success
  type: bool
stdout:
  description: Raw output of the nodetool statusbinary command. Possible values are 'running' or 'not running'.
  returned: success
  type: str
stderr:
  description: Error output of the nodetool command.
  returned: when debug is true
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
        supports_check_mode=True,
    )

    status_cmd = 'statusbinary'
    n = NodeToolCommandSimple(module, status_cmd)

    result = {}

    (rc, out, err) = n.run_command()
    out = out.strip()

    if module.params['debug'] and err:
        result['stderr'] = err

    if rc != 0:
        module.fail_json(name=status_cmd, msg="statusbinary command failed", **result)

    result['stdout'] = out
    result['is_up'] = out == 'running'

    module.exit_json(**result)


if __name__ == '__main__':
    main()
