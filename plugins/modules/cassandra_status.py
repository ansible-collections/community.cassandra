#!/usr/bin/python

# 2020 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_status
author: Rhys Campbell (@rhysmeister)
short_description: Validates the status of the cluster as seen from the node.
requirements:
  - nodetool
description:
    - Validates the status of the cluster as seen from the C* node.
    - Ensure that all nodes are in a UP/NORMAL state or tolerate a few down nodes.
    - Optionally poll multiple times to allow the cluster state to stablise.
    - Cluster status is obtained thtough the usage of the nodetool status command.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  down:
    description:
      - The maximum number of nodes that can be tolerated as down.
    type: int
    default: 0
    aliases:
      - d
  poll:
    description:
      - The maximum number of times to call nodetool status to query cluster status.
    type: int
    default: 1
  interval:
    description:
      - The number of seconds to wait between poll executions.
    type: int
    default: 30
'''

EXAMPLES = '''
- name: Ensure all Cassandra nodes are in the UN (Up/Normal) state.
  community.cassandra.cassandra_status:

- name: Ensure all Cassandra nodes are in the UN (Up/Normal) state polling max 3 times, 60 seconds interval
  community.cassandra.cassandra_status:
    poll: 3
    interval: 60

- name: Ensure down nodes are no more than 1
  community.cassandra.cassandra_status:
    down: 1
'''

RETURN = '''
msg:
  description: A message indicating what has happened.
  returned: on success
  type: bool
rc:
  description: Return code of the last executed command.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
import re
import time
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCmd
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


class NodeToolStatusCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;

        - status_command

    """

    def __init__(self, module):
        NodeToolCmd.__init__(self, module)
        self.status_cmd = "status"

    def status_command(self):
        return self.nodetool_cmd(self.status_cmd)


def nodetool_status_poll(module):
    '''
    Calls NodeToolStatusCommand(module, status_cmd) a maximum of poll times
    with the indicated interval. Returns as soon all nodes are up or the
    previous limits are reached.
    '''
    cluster_status = None  # Last cluster status
    cluster_status_list = []
    iterations = 0
    return_codes = []
    stdout_list = []
    stderr_list = []
    down_running_total = None
    poll = module.params['poll']
    interval = module.params['interval']

    while iterations < poll:
        down_running_total = 0  # reset between iterations
        iterations += 1
        n = NodeToolStatusCommand(module)
        (rc, out, err) = n.status_command()
        stdout_list.append(out.strip())
        stderr_list.append(err.strip())
        return_codes.append(rc)
        if rc == 0:
            cluster_status = cluster_up_down(out)
            cluster_status_list.append(cluster_status)
            for dc in cluster_status.keys():
                down_running_total += len(cluster_status[dc]['down'])
            if down_running_total == 0:
                break  # No down nodes, we're good
            else:
                time.sleep(interval)  # Something is wrong, check again in a bit but
        else:
            if iterations == poll:
                break
            else:
                time.sleep(interval)
    return cluster_status, cluster_status_list, iterations, \
        return_codes, stdout_list, stderr_list, down_running_total


def cluster_up_down(stdout):
    '''
    Extract the Data Centres from the nodetool status stdout
    Returns a dict in the following format...
        {
            "datacenter1":
                "up": [ "1.1.1.1",
                        "1.1.1.2",
                        "1.1.1.3",
                        "1.1.1.4",
                        "1.1.1.5" ],
                "down": [ "1.1.1.6" ],
            "datacenter2":
                "up": [ "1.1.2.1",
                        "1.1.2.2",
                        "1.1.2.3",
                        "1.1.2.4",
                        "1.1.2.5",
                        "1.1.2.6" ],
                "down": []
        }
    '''
    cluster_up_down = {}
    for line in ''.join(stdout).split('\n'):
        if line.startswith("Datacenter"):
            data_center = line.split(' ')[1]
            cluster_up_down[data_center] = dict()
            cluster_up_down[data_center]["up"] = list()
            cluster_up_down[data_center]["down"] = list()
        if line.startswith("UN") and bool(re.findall(r'[0-9]+(?:\.[0-9]+){3}', line)):
            cluster_up_down[data_center]["up"].append(line.split()[1])
        if line.startswith("D") and bool(re.findall(r'[0-9]+(?:\.[0-9]+){3}', line)):
            cluster_up_down[data_center]["down"].append(line.split()[1])
    return cluster_up_down


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        down=dict(type='int', default=0, aliases=["d"]),
        poll=dict(type='int', default=1),
        interval=dict(type='int', default=30)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    down = module.params['down']
    debug = module.params['debug']

    cluster_status, cluster_status_list, iterations, \
        return_codes, stdout_list, stderr_list, down_running_total \
        = nodetool_status_poll(module)

    result = {}

    result['cluster_status'] = cluster_status
    result['iterations'] = iterations

    if debug:
        result['cluster_status_list'] = cluster_status_list
        result['return_codes'] = return_codes
        if stderr_list:
            result['stderr_list'] = stderr_list
        if stdout_list:
            result['stdout_list'] = stdout_list

    # Needs rethink
    if return_codes[-1] == 0:  # Last execution successful
        if down_running_total == 0:
            result['msg'] = "All nodes are in an UP/NORMAL state"
        else:
            if down_running_total > down:
                result['msg'] = "Too many nodes are in a DOWN state"
                module.fail_json(**result)
            else:
                result['msg'] = "Down nodes are within the tolerated level"
    else:
        result['msg'] = "nodetool error: {0}".format(stderr_list[-1])
        result['rc'] = return_codes[-1]
        module.fail_json(**result)

    # Everything is good
    module.exit_json(**result)


if __name__ == '__main__':
    main()
