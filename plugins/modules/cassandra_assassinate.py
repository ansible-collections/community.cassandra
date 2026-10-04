#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_assassinate
author: Rhys Campbell (@rhysmeister)
short_description: Run the assassinate command against a node.
requirements:
  - nodetool
description:
  - Run the assassinate command against a node.
  - Forcefully removes a dead node without re-replicating any data.
  - It is a last resort tool if you cannot successfully use nodetool removenode.
  - The module first runs nodetool status. It fails, without running assassinate,
    when ip_address is up (C(UN), C(UJ), C(UL) or C(UM)) as seen from the node it
    connects to. To remove a live node, decommission it, or stop it and use removenode.
  - When ip_address is not in nodetool status, the module checks nodetool gossipinfo.
    It reports no change when the endpoint is unknown to gossip, or already
    C(LEFT) or C(removed) there (for example after a previous assassinate),
    as seen from the node it connects to. Any other endpoint still in gossip is
    assassinated, whatever its gossip state.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  ip_address:
    description:
      - IP Address of endpoint to assassinate.
      - A hostname, a port or an IPv6 scope is rejected, the module fails without running nodetool.
    type: str
    required: yes
  debug:
    description:
      - Add additional debug output.
    type: bool
    default: false
'''

EXAMPLES = '''
- name: Assassinate a node
  community.cassandra.cassandra_assassinate:
    ip_address: 127.0.0.1
'''

RETURN = '''
msg:
  description: A short description of what happened.
  returned: always
  type: str
'''

try:
    import ipaddress
    HAS_IPADDRESS = True
except ImportError:  # Python 2
    HAS_IPADDRESS = False

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible.module_utils.common.text.converters import to_text
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec
from ansible_collections.community.cassandra.plugins.module_utils.nodetool_status import gossip_status, ring_state


# Gossip STATUS of an endpoint that has already left the ring
GONE_STATUSES = ('LEFT', 'removed')


def run_nodetool(module, cmd, result):
    """Run a nodetool sub-command, fail on error, return its stripped output."""
    (rc, out, err) = NodeToolCommandSimple(module, cmd).run_command()
    out = out.strip()
    err = err.strip()
    if rc != 0:
        result['msg'] = "nodetool {0} did not execute successfully rc: {1}".format(cmd.split()[0], rc)
        result['rc'] = rc
        if module.params['debug'] and out:
            result['stdout'] = out
        if err:
            result['stderr'] = err
        module.fail_json(**result)
    return out, err


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        ip_address=dict(type='str', required=True),
        debug=dict(type='bool', default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_IPADDRESS:
        module.fail_json(msg=missing_required_lib('ipaddress'))

    ip_address = module.params['ip_address']
    result = {'changed': False}
    try:
        ipaddress.ip_address(to_text(ip_address))
        if '%' in ip_address:
            raise ValueError
    except ValueError:
        result['msg'] = "ip_address must be an IP address (not a hostname, no port): {0}".format(ip_address)
        module.fail_json(**result)

    state = ring_state(run_nodetool(module, 'status', result)[0], ip_address)
    if state is not None and state[0] == 'U':
        result['msg'] = ("{0} is {1}, a live node: assassinate only removes a dead one. "
                         "Decommission it, or stop it and use removenode".format(ip_address, state))
        module.fail_json(**result)
    if state is None:
        status = gossip_status(run_nodetool(module, 'gossipinfo', result)[0], ip_address)
        if status is None or status in GONE_STATUSES:
            result['msg'] = "{0} is not in the cluster".format(ip_address)
            module.exit_json(**result)

    msg = "nodetool assassinate executed successfully for endpoint: {0}".format(ip_address)
    if module.check_mode:
        module.exit_json(changed=True, msg=msg + " (check mode)")
    (out, err) = run_nodetool(module, 'assassinate -- {0}'.format(ip_address), result)
    result['changed'] = True
    result['msg'] = msg
    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err
    module.exit_json(**result)


if __name__ == '__main__':
    main()
