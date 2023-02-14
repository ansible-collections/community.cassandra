#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_batchlogreplaythrottle
author: Rhys Campbell (@rhysmeister)
short_description: Sets the batch log replay throttle.
requirements:
  - nodetool
description:
    - Sets the batch log replay throttle.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  value:
    description:
      - KB value to set batch log replay throttle to.
    type: int
    required: True
'''

EXAMPLES = '''
- name: Set batchlogreplaythrottle with module
  cassandra_batchlogreplaythrottle:
    value: 1024
'''

RETURN = '''
msg:
  description: A breif description of what happened
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

    set_cmd = "setbatchlogreplaythrottle  {0}".format(module.params['value'])
    get_cmd = "getbatchlogreplaythrottle"
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

    get_response = "Batchlog replay throttle: {0} KB/s".format(value)
    if get_response == out:

        if rc != 0:
            result['changed'] = False
            module.fail_json(name=get_cmd,
                             msg="{0} command failed".format(get_cmd), **result)
        else:
            result['changed'] = False
            result['msg'] = "Batch log replay throttle is already {0} KB/s".format(value)
    else:

        if module.check_mode:
            result['changed'] = True
            result['msg'] = "Batch log replay throttle updated"
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
                                 msg="{0} command failed".format(set_cmd), **result)
            else:
                result['changed'] = True
                result['msg'] = "Batch log replay throttle updated"

    module.exit_json(**result)


if __name__ == '__main__':
    main()
