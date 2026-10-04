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
      - Forces completion of a pending removal (runs C(nodetool removenode force)).
      - Use it when a previous removal of host_id is stuck.
      - C(nodetool removenode force) takes no host id and finishes B(every) pending
        removal on the cluster, not only the one of host_id.
      - It only runs when host_id is down and leaving (C(DL)) in nodetool status,
        that is a dead node being removed (or a decommissioning node that went down).
        The module fails when host_id is in the ring in any other state, including
        C(UL) (a live node decommissioning), and reports no change when host_id is
        no longer in the ring.
      - With host_id C(DL), it also fails, forcing nothing, when any other node is
        leaving (C(UL), C(DL) or C(?L)).
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

- name: Force completion of a pending removal
  community.cassandra.cassandra_removenode:
    host_id: "07a8a3b1-98e7-4ed9-8481-b328489ad711"
    force: true
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
from ansible_collections.community.cassandra.plugins.module_utils.nodetool_status import NODE_RE, node_state


# TODO add to common and unit test
def valid_uuid(uuid):
    regex = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z', re.I)
    match = regex.match(uuid)
    return bool(match)


def leaving_nodes(status_out):
    """Return the host ids of the nodes leaving (UL, DL or ?L) in nodetool status output."""
    leaving = []
    for line in status_out.splitlines():
        if NODE_RE.match(line) and line[1] == "L":
            leaving.extend(f for f in line.split() if valid_uuid(f))
    return leaving


def removenode_cmd(host_id, force):
    # nodetool removenode force takes no host id: it forces every pending removal
    if force:
        return "removenode force"
    return "removenode -- {0}".format(host_id)


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

    host_id = module.params['host_id'].strip().lower()
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
        state = node_state(out, host_id)
        if force and state == "UL":
            result['msg'] = ("{0} is UL: a live node leaving (decommission), "
                             "not a removal; nothing forced".format(host_id))
            module.fail_json(**result)
        if force and state == "DN":
            result['msg'] = ("no removal of {0} in progress: "
                             "run it without force first".format(host_id))
            module.fail_json(**result)
        if force and state is not None and state != "DL":
            result['msg'] = ("{0} is {1}, not a removal in progress; "
                             "nothing forced".format(host_id, state))
            module.fail_json(**result)
        if force and state == "DL":
            others = [h for h in leaving_nodes(out) if h != host_id]
            if others:
                result['msg'] = ("other nodes are leaving ({0}): removenode force "
                                 "would force them too; nothing forced".format(", ".join(others)))
                module.fail_json(**result)
        if state is not None:  # host is still in ring
            cmd = removenode_cmd(host_id, force)
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
