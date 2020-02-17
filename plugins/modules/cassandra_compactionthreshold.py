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
module: cassandra_compactionthreshold
author: Rhys Campbell (@rhysmeister)
version_added: 2.8
short_description: Sets the compaction threshold.
requirements: [ nodetool ]
description:
    - Sets the compaction threshold.
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
  keyspace:
    description:
      - The keyspace to adjust compaction thresholds for.
    type: str
    required: True
  table:
    description:
      - The table to adjust compaction thresholds for.
    type: str
    required: True
  min:
    description: >
      Sets the minimum number of SSTables to trigger a minor compaction when
      using SizeTieredCompactionStrategy or DateTieredCompactionStrategy.
    type: int
    required: True
  max:
    description: >
      Sets the maximum number of SSTables to allow in a minor compaction when
      using SizeTieredCompactionStrategy or DateTieredCompactionStrategy.
    type: int
    required: True
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
- name: Adjust compactionthreshold with module
  cassandra_compactionthreshold:
    keyspace: system
    table: local
    min: 8
    max: 64
'''

RETURN = '''
cassandra_compactionthreshold:
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


class NodeToolGetSetCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;

        - get_cmd
        - set_cmd
    """

    def __init__(self, module, get_cmd, set_cmd):
        NodeToolCmd.__init__(self, module)
        self.get_cmd = get_cmd
        self.set_cmd = set_cmd

    def get_command(self):
        return self.nodetool_cmd(self.get_cmd)

    def set_command(self):
        return self.nodetool_cmd(self.set_cmd)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', default=None),
            port=dict(type='int', default=7199),
            password=dict(type='str', no_log=True),
            password_file=dict(type='str', no_log=True),
            username=dict(type='str', no_log=True),
            keyspace=dict(type='str', required=True),
            table=dict(type='str', required=True),
            min=dict(type='int', required=True),
            max=dict(type='int', required=True),
            nodetool_path=dict(type='str', default=None, required=False),
            debug=dict(type='bool', default=False, required=False),
        ),
        supports_check_mode=True
    )

    keyspace = module.params['keyspace']
    table = module.params['table']
    min = module.params['min']
    max = module.params['max']
    set_cmd = "setcompactionthreshold {0} {1} {2} {3}".format(keyspace,
                                                              table,
                                                              min,
                                                              max)
    get_cmd = "getcompactionthreshold {0} {1}".format(keyspace, table)

    n = NodeToolGetSetCommand(module, get_cmd, set_cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.get_command()
    out = out.strip()

    if out:
        result['stdout'] = out
    if err:
        result['stderr'] = err

    get_response = "Current compaction thresholds for {0}/{1}: \n min = {2},  max = {3}".format(keyspace, table, min, max)
    if get_response == out:

        if rc != 0:
            result['changed'] = False
            module.fail_json(name=get_cmd,
                             msg="get command failed", **result)
    else:

        if module.check_mode:
            result['changed'] = True
        else:
            (rc, out, err) = n.set_command()
            out = out.strip()
            if out:
                result['stdout'] = out
            if err:
                result['stderr'] = err
            if rc != 0:
                result['changed'] = False
                module.fail_json(name=set_cmd,
                                 msg="set command failed", **result)
            else:
                result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
