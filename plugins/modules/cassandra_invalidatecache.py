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
  fake_counter:
    description:
      - Fake the counter results so the module wil execute the appropriate invalid cache command.
      - Intended for internal testing use only.
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

from ansible.module_utils.basic import AnsibleModule
import re
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCommandSimple
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def parse_cache_info(info, module, fake_counter):
    """
    This function parses the output from the nodetool  info command
    in order to return the cache info, i.e.
    'ID                     : f4ee490c-df8e-4a8d-9236-320903697fbf
    Gossip active          : true
    Native Transport active: true
    Load                   : 145.17 KiB
    Generation No          : 1638800353
    Uptime (seconds)       : 225798
    Heap Memory (MB)       : 258.26 / 495.00
    Off Heap Memory (MB)   : 0.00
    Data Center            : datacenter1
    Rack                   : rack1
    Exceptions             : 10
    Key Cache              : entries 10, size 896 bytes, capacity 24 MiB, 48 hits, 62 requests, 0.774 recent hit rate, 14400 save period in seconds
    Row Cache              : entries 0, size 0 bytes, capacity 0 bytes, 0 hits, 0 requests, NaN recent hit rate, 0 save period in seconds
    Counter Cache          : entries 0, size 0 bytes, capacity 12 MiB, 0 hits, 0 requests, NaN recent hit rate, 7200 save period in seconds
    Percent Repaired       : 100.0%
    Token                  : -6148914691236517206'

    {
      "key_cache_entries": 10,
      "row_cache_entries": 0,
      "counter_cache_entries": 0
    }

    TODO - This should be placed into common code and unit tested
    """
    key_cache_entries = None
    row_cache_entries = None
    counter_cache_entries = None
    try:
        if fake_counter:
            key_cache_entries = 100
            row_cache_entries = 100
            counter_cache_entries = 100
        else:
            p = re.compile(r"Key Cache .*: entries \d+")
            key_cache_entries = int(p.search(info).group(0).split()[-1:][0])
            p = re.compile(r"Row Cache .*: entries \d+")
            row_cache_entries = int(p.search(info).group(0).split()[-1:][0])
            p = re.compile(r"Counter Cache .*: entries \d+")
            counter_cache_entries = int(p.search(info).group(0).split()[-1:][0])
    except Exception as excep:
        module.fail_json(msg="Error parsing info output: {0}".format(excep))
    if key_cache_entries is None or row_cache_entries is None or counter_cache_entries is None:
        module.fail_json(msg="Unable to get cache info")
    return {"key_cache_entries": key_cache_entries,
            "row_cache_entries": row_cache_entries,
            "counter_cache_entries": counter_cache_entries}


def main():

    cache_choices = ["counter", "key", "row"]

    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        cache=dict(type='str', required=True, choices=cache_choices),
        debug=dict(type='bool', default=False),
        fake_counter=dict(type='bool', default=False)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    result = {}

    cmd = "info"
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

        cache = module.params['cache']
        cmd = 'invalidate{0}cache'.format(cache)
        fake_counter = module.params['fake_counter']
        cache_info = parse_cache_info(out, module, fake_counter)

        if cache == "key" and cache_info['key_cache_entries'] > 0 or cache == "row" and cache_info['row_cache_entries'] > 0 \
                or cache == "counter" and cache_info['counter_cache_entries'] > 0:
            n = NodeToolCommandSimple(module, cmd)

            rc = None
            out = ''
            err = ''
            result = {}

            if module.check_mode is False:
                (rc, out, err) = n.run_command()
            else:
                rc = 0
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
            else:
                result['msg'] = "Failed invalidating the {0} cache".format(cache)
                module.fail_json(**result)
        else:
            result['msg'] = "The {0} cache is empty".format(cache)
            result['changed'] = False
    else:
        result['msg'] = "Failed getting cache info"
        module.fail_json(**result)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
