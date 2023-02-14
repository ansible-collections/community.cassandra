#!/usr/bin/python

# 2021 Rhys Campbell rhyscampbell@bluewin.ch
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_reload
author: Rhys Campbell (@rhysmeister)
short_description: Reloads various objects into the local node.
requirements:
  - nodetool
description:
  - Reloads various objects into the local node.
  - Currently can reload local schema, seeds, ssl certs and triggers.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  reload:
    description:
      - Object type to reload.
    type: str
    required: true
    choices:
      - localschema
      - seeds
      - ssl
      - triggers
'''

EXAMPLES = '''
- name: Reload local schema
  community.cassandra.cassandra_reload:
    reload: localschema

- name: Reload seeds
  community.cassandra.cassandra_reload:
    reload: seeds

- name: Reload ssl certs
  community.cassandra.cassandra_reload:
    reload: ssl

- name: Reload triggers
  community.cassandra.cassandra_reload:
    reload: triggers
'''

RETURN = '''
cassandra_reload:
  description: The return state of the executed command.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():
    reload_choices = ['localschema',
                      'seeds',
                      'ssl',
                      'triggers']
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        reload=dict(type='str', choices=reload_choices, required=True)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    cmd = "reload{0}".format(module.params['reload'])
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
        result['msg'] = "nodetool {0} executed successfully".format(cmd)
        module.exit_json(**result)
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool {0} did not execute successfully".format(cmd)
        module.exit_json(**result)


if __name__ == '__main__':
    main()
