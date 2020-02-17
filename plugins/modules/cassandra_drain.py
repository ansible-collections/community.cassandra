#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule, load_platform_subclass
import socket
__metaclass__ = type

ANSIBLE_METADATA =\
    {"metadata_version": "1.1",
     "status": "['preview']",
     "supported_by": "community"}

DOCUMENTATION = '''
---
module: cassandra_cleanup
author: "Rhys Campbell"
version_added: 2.8
short_description: Drains a Cassandra node.
requirements: [ nodetool ]
description:
    - Flushes all memtables from the node to SSTables on disk.
    - Cassandra stops listening for connections from the client and other nodes.
    - Restart Cassandra after running nodetool drain.
    - Use this command before upgrading a node to a new version of Cassandra.
options:
  host:
    description:
      - The hostname.
    type: str
    default: "localhost"
  port:
    description:
      - The Cassandra TCP port.
    type: int
    default: 7199
  password:
    description:
      - The password to authenticate with.
    type: str
  password_file:
    description:
      - Path to a file containing the password.
    type: str
  username:
    description:
      - The username to authenticate with.
    type: str
  nodetool_path:
    description:
      - The path to nodetool.
    type: str
'''

EXAMPLES = '''
- name: Drain Cassandra Node
  cassandra_drain:
'''

RETURN = '''
cassandra_drain:
  description: The return state of the executed command.
  returned: success
  type: str
'''


class NodeToolCmd(object):
    """
    This is a generic NodeToolCmd class for building nodetool commands
    """

    def __init__(self, module):
        self.module = module
        self.host = module.params['host']
        self.port = module.params['port']
        self.password = module.params['password']
        self.password_file = module.params['password_file']
        self.username = module.params['username']
        self.nodetool_path = module.params['nodetool_path']
        if self.host is None:
            self.host = socket.getfqdn()

    def execute_command(self, cmd):
        return self.module.run_command(cmd)

    def nodetool_cmd(self, sub_command):
        if self.nodetool_path is not None and len(self.nodetool_path) > 0 and \
                not self.nodetool_path.endswith('/'):
            self.nodetool_path += '/'
        else:
            self.nodetool_path = ""
        cmd = "{0}nodetool --host {1} --port {2}".format(self.nodetool_path,
                                                         self.host,
                                                         self.port)
        if self.username is not None:
            cmd += " --username {0}".format(self.username)
            if self.password_file is not None:
                cmd += " --password-file {0}".format(self.password_file)
            else:
                cmd += " --password '{0}'".format(self.password)
        # The thing we want nodetool to execute
        cmd += " {0}".format(sub_command)
        return self.execute_command(cmd)


class NodeToolCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;

        - run_command
    """

    def __init__(self, module, cmd):
        NodeToolCmd.__init__(self, module)
        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', default=None),
            port=dict(type='int', default=7199),
            password=dict(type='str', no_log=True),
            password_file=dict(type='str', no_log=True),
            username=dict(type='str', no_log=True),
            nodetool_path=dict(type='str', default=None, required=False)),
        supports_check_mode=False)

    cmd = 'drain'

    n = NodeToolCommand(module, cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.run_command()
    out = out.strip()
    if out:
        result['stdout'] = out
    if err:
        result['stderr'] = err

    if rc == 0:
        result['changed'] = True
        result['msg'] = "nodetool drain executed successfully"
        module.exit_json(**result)
    else:
        result['rc'] = rc
        result['changed'] = False
        result['msg'] = "nodetool drain did not execute successfully"
        module.exit_json(**result)


if __name__ == '__main__':
    main()
