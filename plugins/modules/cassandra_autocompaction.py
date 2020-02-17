#!/usr/bin/python

# 2019 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule, load_platform_subclass
__metaclass__ = type

ANSIBLE_METADATA =\
    {"metadata_version": "1.1",
     "status": "['preview']",
     "supported_by": "community"}

DOCUMENTATION = '''
---
module: cassandra_autocompaction
author: Rhys Campbell (@rhysmeister)
version_added: 2.8
short_description: Enabled or disables autocompaction.
requirements: [ nodetool ]
description:
    - Enabled or disables autocompaction.
options:
  host:
    description:
      - The hostname.
    type: str
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
  keyspace:
    description:
      - The keyspace to operate on.
    type: str
    required: true
  table:
    description:
      - The table to operate on.
    type: list
    required: true
  state:
    description:
      - The required status
    choices:
      - "enabled"
      - "disabled"
    required: true
  nodetool_path:
    description:
      - The path to nodetool.
    type: str
  debug:
    description:
      - Enable additional debug output.
    type: bool
'''

EXAMPLES = '''
- name: Ensure Cassandra Autocompaction is enabled
  cassandra_autocompaction:
    keyspace: system
    table: local
    state: enabled

- name: Ensure Cassandra Autocompaction is disabled
  cassandra_autocompaction:
    keyspace: system
    table: local
    state: disabled
'''

RETURN = '''
cassandra_autocompaction:
  description: The return state of the executed command.
  returned: success
  type: str
'''

import socket


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
        self.debug = module.params['debug']
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
        if self.debug:
            self.module.debug(cmd)
        return self.execute_command(cmd)


class NodeTool2PairCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;

        - enable_command
        - disable_command
    """

    def __init__(self, module, enable_cmd, disable_cmd):
        NodeToolCmd.__init__(self, module)
        self.enable_cmd = enable_cmd
        self.disable_cmd = disable_cmd

    def enable_command(self):
        return self.nodetool_cmd(self.enable_cmd)

    def disable_command(self):
        return self.nodetool_cmd(self.disable_cmd)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', default=None),
            port=dict(type='int', default=7199),
            password=dict(type='str', no_log=True),
            password_file=dict(type='str', no_log=True),
            username=dict(type='str', no_log=True),
            keyspace=dict(type='str', required=True),
            table=dict(type='list', required=True),
            state=dict(required=True, choices=['enabled', 'disabled']),
            nodetool_path=dict(type='str', default=None, required=False),
            debug=dict(type='bool', default=False, required=False),
        ),
        supports_check_mode=False
    )

    keyspace = module.params['keyspace']
    table = ' '.join(module.params['table'])
    enable_cmd = 'enableautocompaction {0} {1}'.format(keyspace, table)
    disable_cmd = 'disableautocompaction {0} {1}'.format(keyspace, table)

    n = NodeTool2PairCommand(module, enable_cmd, disable_cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    # We don't know if this has changed or not
    if module.params['state'] == "enabled":

        (rc, out, err) = n.enable_command()
        out = out.strip()

        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

        if rc != 0:
            module.fail_json(name=enable_cmd,
                             msg="enable command failed", **result)
        else:
            result['changed'] = True

    elif module.params['state'] == "disabled":

        (rc, out, err) = n.disable_command()
        out = out.strip()

        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

        if rc != 0:
            module.fail_json(name=disable_cmd,
                             msg="disable command failed", **result)
        else:
            result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
