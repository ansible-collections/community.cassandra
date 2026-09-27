#!/usr/bin/python

# 2026 Alain Rodriguez <alain@casterix.fr>
# https://github.com/arodrime
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_netstats
author: Alain Rodriguez (@arodrime)
short_description: Returns the mode of the node and whether it is streaming.
version_added: 2.1.0
requirements:
  - nodetool
description:
    - Runs nodetool netstats and returns the operating mode of the node
      (STARTING, JOINING, NORMAL, LEAVING, DECOMMISSIONED, DRAINING, DRAINED...)
      and whether it is streaming data (bootstrap, rebuild, repair...).
    - Never changes anything.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options
'''

EXAMPLES = '''
- name: Wait until the node has joined the ring
  community.cassandra.cassandra_netstats:
  register: netstats
  until: netstats.mode | default('') == 'NORMAL'
  retries: 60
  delay: 10

- name: Fail if the node is streaming
  community.cassandra.cassandra_netstats:
  register: netstats
  failed_when: netstats.streaming
'''

RETURN = '''
mode:
  description:
    - Operating mode of the node, as in the "Mode:" line.
    - Empty string when the output has no "Mode:" line.
  returned: success
  type: str
  sample: NORMAL
streaming:
  description: True if the node has stream sessions in progress.
  returned: success
  type: bool
streams:
  description: The stream sessions part of the output, empty when not streaming.
  returned: success
  type: list
  elements: str
stdout:
  description: Raw output of the nodetool netstats command.
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
from ansible_collections.community.cassandra.plugins.module_utils.nodetool_netstats import parse_netstats


def main():
    argument_spec = cassandra_common_argument_spec()
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    cmd = 'netstats'
    n = NodeToolCommandSimple(module, cmd)

    result = {}

    (rc, out, err) = n.run_command()

    if module.params['debug'] and err:
        result['stderr'] = err

    if rc != 0:
        module.fail_json(name=cmd, msg="netstats command failed", **result)

    mode, streams = parse_netstats(out)
    result['stdout'] = out
    result['mode'] = mode
    result['streams'] = streams
    result['streaming'] = len(streams) > 0

    module.exit_json(**result)


if __name__ == '__main__':
    main()
