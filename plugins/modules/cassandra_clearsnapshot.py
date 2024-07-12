#!/usr/bin/python

# 2024 Jaymit Patel <18jaymit@gmail.com>
# https://github.com/jaymitp
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_clearsnapshot
author: Jaymit Patel (@jaymitp)
short_description: Removes one or more snapshots.
requirements:
  - nodetool
description:
    - Removes one or more snapshots. 
    - To remove all snapshots, omit the snapshot name.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  keyspace:
    description:
      - Optional keyspace to remove snapshots from
    type: list
    elements: str
  name:
    description:
      - Optional name of the snapshot to remove
    type: str
    aliases:
      - tag
      - t
  debug:
    description:
      - Add additional debug to module output. 
    type: bool
    default: False 
'''

EXAMPLES = '''
- name: Remove all snapshots on the node
  community.cassandra.cassandra_clearsnapshot:

- name: Remove snapshots from multiple keyspaces on the node
  community.cassandra.cassandra_clearsnapshot:
    keyspace: 
      - keyspace1
      - keyspace2

- name: Remove all snapshots named 01-01-2024 from multiple keyspaces
  community.cassandra.cassandra_clearsnapshot:
    keyspace: 
      - keyspace1
      - keyspace2
    name: 01-01-2024
'''

RETURN = '''
msg:
  description: A message indicating what has happened.
  returned: on success
  type: str
rc:
  description: Return code of the last executed command.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolCmd
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


class NodeToolClearSnapshotCommand(NodeToolCmd):

    """ 
    Inherits from the NodeToolCmd class. Adds the following methods;     
        - run_command 
    """ 
    def __init__(self, module, cmd): 
        NodeToolCmd.__init__(self, module) 
        self.keyspace = module.params["keyspace"]
        self.name = module.params["name"]
      
        if self.name is not None:
            cmd = "{0} -t {1}".format(cmd, self.name)
        else:
            cmd = "{0} --all".format(cmd)
        if self.keyspace is not None:
            cmd = "{0} {1}".format(cmd, " ".join(self.keyspace))
        self.cmd = cmd
 
    def run_command(self): 
       return self.nodetool_cmd(self.cmd) 


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        keyspace=dict(type='list', elements='str', default=None, required=False),
        name=dict(type='str', default=None, aliases=['tag','t'], required=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )
    
    cmd = "clearsnapshot"

    n = NodeToolClearSnapshotCommand(module, cmd)

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
        result['msg'] = "nodetool clearsnapshot executed successfully"
        module.exit_json(**result)
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool clearsnapshot did not execute successfully"
        module.exit_json(**result)


if __name__ == '__main__':
    main()
