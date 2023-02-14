#!/usr/bin/python

# 2021 Rhys Campbell rhyscampbell@bluewin.ch
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_compact
author: Rhys Campbell (@rhysmeister)
short_description: Manage compaction on the Cassandra node.
requirements:
  - nodetool
description:
    - Manage compaction on the Cassandra node.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  compact:
    description:
      - The required status
    type: bool
    default: true
'''

EXAMPLES = '''
- name: RUu compaction on the node
  community.cassandra.cassandra_compact:
    compaction: yes

- name: Stop compaction on the node
  community.cassandra.cassandra_compact:
    compaction: no
'''

RETURN = '''
cassandra_compact:
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
        compact=dict(default=True, type='bool')
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    status_cmd = 'compactionstats'
    enable_cmd = 'compact'
    disable_cmd = 'stop'
    status_inactive = 'pending tasks: 0'

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

    if module.params['compact'] is False:

        if rc != 0:
            module.fail_json(name=status_cmd,
                             msg="{0} command failed".format(status_cmd), **result)
        if module.check_mode:
            if out != status_inactive:
                module.exit_json(changed=True, msg="compaction stopped (check mode)", **result)
            else:
                module.exit_json(changed=False, msg="compaction is not running", **result)
        if out != status_inactive:
            (rc, out, err) = n.disable_command()
            result['msg'] = "compaction stopped"
            result['changed'] = True
            if module.params['debug']:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
            if rc != 0:
                module.fail_json(name=disable_cmd,
                                 msg="{0} command failed".format(disable_cmd), **result)
        else:
            result['msg'] = "compaction is not running"
            result['changed'] = False

    elif module.params['compact'] is True:

        if rc != 0:
            module.fail_json(name=status_cmd,
                             msg="{0} command failed".format(status_cmd), **result)
        if module.check_mode:
            if out == status_inactive:
                module.exit_json(changed=True, msg="compaction started (check mode)", **result)
            else:
                module.exit_json(changed=False, msg="compaction is already running", **result)
        if out == status_inactive:
            (rc, out, err) = n.enable_command()
            result['msg'] = "compaction started"
            result['changed'] = True
            if module.params['debug']:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
            if rc is not None and rc != 0:
                module.fail_json(name=enable_cmd,
                                 msg="{0} command failed".format(enable_cmd), **result)
        else:
            result['msg'] = "compaction is already running"
            result['changed'] = False

    module.exit_json(**result)


if __name__ == '__main__':
    main()
