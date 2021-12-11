#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_invalidatecache
author: Rhys Campbell (@rhysmeister)
short_description: Invalidates the various caches on the Cassandra node.
requirements:
  - nodetool
description:
  - Invalidates the various caches on the Cassandra node.
  - Invalidates the Counter, Key and Row caches.
  - This module is not idempotent.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  cache:
    description:
      - The cache to clear.
    type: str
    required: yes
    choices:
      - "counter"
      - "key"
      - "row"
  debug:
    description:
      - Add additional debug output.
    type: bool
    default: false
'''

EXAMPLES = '''
- name: Invalidate the counter cache
  community.cassandra.cassandra_invalidatecache:
    cache: counter

- name: Invalidate the key cache
  community.cassandra.cassandra_invalidatecache:
    cache: key

- name: Invalidate the row cache
  community.cassandra.cassandra_invalidatecache:
    cache: row
'''

RETURN = '''
msg:
  description: A short description of what happened.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule, load_platform_subclass
import socket
import subprocess
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCmd, NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():

    cache_choices = ["counter", "key", "row"]

    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        cache=dict(type='str', required=True, choices=cache_choices),
        debug=dict(type='bool', default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    cache = module.params['cache']
    
    cmd = 'invalidate{0}cache'.format(cache)

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
        result['msg'] = "The {0} cache was invalidated".format(cache)
        module.exit_json(**result)
    else:
        result['msg'] = "Failed invalidating the {0} cache".format(cache)
        module.fail_json(**result)


if __name__ == '__main__':
    main()
