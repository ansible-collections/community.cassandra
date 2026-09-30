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
    - Acts on the node reached through I(host) and I(port) (JMX), according to its mode
      (C(Mode:) line of C(nodetool netstats)).
    - C(NORMAL) runs C(nodetool decommission).
    - C(DECOMMISSIONED) and C(LEAVING) (a decommission in progress) change nothing.
    - C(DECOMMISSION_FAILED) (Cassandra 5.0+) fails. On Cassandra 4.0 and 4.1 a failed
      decommission stays C(LEAVING).
    - A failed decommission is never retried by the module; its cause (disk space on the
      receiving nodes, network, timeouts) must be understood first. Running
      C(nodetool decommission) again by hand resumes it (ranges already transferred are
      skipped).
    - Any other mode (C(STARTING), C(JOINING), C(MOVING), C(DRAINING), C(DRAINED), ...),
      or no mode, fails.

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
  returned: always
  type: str
rc:
  description: Return code of the nodetool command that failed.
  returned: on failure of a nodetool command
  type: int
stdout:
  description: Output of nodetool netstats, or of nodetool decommission when it printed something.
  returned: when I(debug) is true and the output is not empty
  type: str
stderr:
  description: Error output of nodetool netstats, or of nodetool decommission when it printed something.
  returned: when I(debug) is true and the error output is not empty
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def node_mode(netstats_out):
    """Return the mode from the "Mode: X" line of nodetool netstats, None if absent."""
    for line in netstats_out.splitlines():
        if line.startswith("Mode:"):
            return line.split(":", 1)[1].strip()
    return None


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

    # The node's own mode, from netstats (the JMX host, often 127.0.0.1,
    # is not necessarily the node's address in the ring).
    n = NodeToolCommandSimple(module, "netstats")

    (rc, out, err) = n.run_command()
    out = out.strip()
    err = err.strip()
    if debug:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

    if rc != 0:
        result['msg'] = "nodetool netstats failed: not decommissioning"
        result['rc'] = rc
        module.fail_json(**result)

    mode = node_mode(out)
    if mode == "DECOMMISSIONED":
        result['changed'] = False
        result['msg'] = "already decommissioned"
    elif mode == "LEAVING":
        result['changed'] = False
        result['msg'] = ("decommission already in progress on this node (on 4.0/4.1 a failed "
                         "decommission also stays LEAVING: check the logs)")
    elif mode == "DECOMMISSION_FAILED":
        result['msg'] = ("the previous decommission of this node failed: find the cause in the logs "
                         "(disk space on the receiving nodes, network, timeouts), then run nodetool "
                         "decommission by hand to resume it")
        module.fail_json(**result)
    elif mode is None:
        result['msg'] = "no Mode line in the nodetool netstats output: not decommissioning"
        module.fail_json(**result)
    elif mode != "NORMAL":
        result['msg'] = "node mode is {0}, not NORMAL: not decommissioning".format(mode)
        module.fail_json(**result)
    else:
        result['changed'] = True
        result['msg'] = "decommission command succeeded"
        if not module.check_mode:
            n = NodeToolCommandSimple(module, "decommission")
            (rc, out, err) = n.run_command()
            out = out.strip()
            err = err.strip()
            if debug:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
            if rc != 0:
                result['changed'] = False
                result['msg'] = "decommission command failed"
                result['rc'] = rc
                module.fail_json(**result)
    module.exit_json(**result)


if __name__ == '__main__':
    main()
