#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_removenode
author: Rhys Campbell (@rhysmeister)
short_description: Removes a node by the given host id from the cluster.
requirements:
  - nodetool
description:
    - Removes a node by the given host id from the cluster.
    - Identify the node by the host id as given in nodetool status output.
    - The nodetool status command is used to determine if the host_id exists in the cluster.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  host_id:
    description:
      - Host Id of the node to rmeove.
    type: str
    required: true
  force:
    description:
      - Forces completion of the pending removal.
    type: bool
    default: false
  debug:
    description:
      - Add additional debug to module output.
    type: bool
    default: False
'''

EXAMPLES = '''
- name: Decommission a node
  community.cassandra.cassandra_removenode:
    host_id: "2d29b2bc-faa5-4837-935c-41c3945119e2"

- name: Force removal of a node
  community.cassandra.cassandra_removenode:
    host_id: "07a8a3b1-98e7-4ed9-8481-b328489ad711"
    force: yes
'''

RETURN = '''
msg:
  description: A message indicating what has happened.
  returned: always
  type: bool
rc:
  description: Return code of executed command
  returned: on failure
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
import re
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


# TODO add to common and unit test
def valid_uuid(uuid):
    regex = re.compile('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', re.I)
    match = regex.match(uuid)
    return bool(match)


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        host_id=dict(type='str', required=True),
        force=dict(type='bool', default=False),
        debug=dict(type='bool', default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    host_id = module.params['host_id']
    force = module.params['force']
    if not valid_uuid(host_id):
        module.fail_json(msg="host_id is not a valid uuid")

    result = {}

    cmd = "status"

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
        if host_id in out:  # host is still in ring
            if force:
                cmd = "removenode -- force {0}".format(host_id)
            else:
                cmd = "removenode -- {0}".format(host_id)
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
                    result['msg'] = "removenode command succeeded"
                else:
                    result['msg'] = "removenode command failed"
                    result['rc'] = rc
                    module.fail_json(**result)
            else:
                result['changed'] = True
                result['msg'] = "removenode command succeeded"
        else:
            result['changed'] = False
            result['msg'] = "host_id does not exist in the cluster"
        module.exit_json(**result)
    else:
        result['msg'] = "removenode command failed"
        result['rc'] = rc
        module.fail_json(**result)

    # Everything is good
    module.exit_json(**result)


if __name__ == '__main__':
    main()
