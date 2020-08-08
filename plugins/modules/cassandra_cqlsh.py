#!/usr/bin/python

# 2020 Rhys Campbell <rhys.james.campbell@googlemail.com>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_cqlsh
author: Rhys Campbell (@rhysmeister)
short_description: Run cql commands via the clqsh shell.
requirements: [ nodetool ]
description:
    - Run cql commands via the clqsh shell.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  cqlsh_host:
    description:
      - Host to connect to
    type: str
    default: localhost
  cqlsh_port:
    description:
      - Port to connect to.
    type: int
    default: 9042
  username:
    description:
      - The C* user to authenticate with.
    type: str
  password:
    description:
      - The C* users password.
    type: str
  keyspace:
    description:
      - Authenticate to the given keyspace
    type: str
  file:
    description:
      - Path to a file containign cql commands.
    type: str
  execute:
    description:
      - cqlsh command to execute.
    type: str
  encoding:
    description:
      - Specify a non-default encoding for output.
    type: str
    default: utf-8
  cqlshrc:
    description:
      - Specify an alternative cqlshrc file location.
    type: str
  cqlversion:
    description:
      - Specify a particular CQL version.
    type: str
  protocol_version:
    description:
      - Specify a specific protcol version.
    type: str
  connect_timeout:
    description:
      - Specify the connection timeout in seconds.
    type: int
    int: 5
  request_timeout:
    description:
      - Specify the default request timeout in seconds.
    type: int
    default: 10
  tty:
    description:
      - Force tty mode
    type: bool
    default: false
  debug:
    description:
      - show additional debug info.
    type: bool
    default: false
  ssl:
    description:
      - Use SSL.
    type: bool
    default: false
  no_compact:
    description:
      - No Compact.
    type: bool
    default: false
  cqlsh_cmd:
    description:
      - cqlsh executable
    type: str
    default: "cqlsh"
'''

EXAMPLES = '''
- name: RUn the DESC KEYSPACES cql command
  community.cassandra.cassandra_cqlsh:
    execute: "DESC KEYSPACES"

- name: Run a file containing cql commands
  community.cassandra.cassandra_cqlsh:
    file: "/path/to/cql/file.sql"
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
results:
  description: Results of whatever cql command was executed.
  returned: on success
  type: raw
'''

from ansible.module_utils.basic import AnsibleModule, load_platform_subclass
import socket
import re
import time
__metaclass__ = type


def add_arg_to_cmd(cmd_list, param_name, param_value, is_bool=False):
    """
    @cmd_list - List of cmd args.
    @param_name - Param name / flag.
    @param_value - Value of the parameter
    @is_bool - Flag is a boolean and has no value.
    """
    if is_bool is False and param_value is not None:
        cmd_list.append(param_name)
        cmd_list.append(param_value)
    elif is_bool is True:
        cmd_list.append(param_name)
    return cmd_list


def main():
    argument_spec = dict(
        cqlsh_host=dict(type='str', default='localhost'),
        cqlsh_port=dict(type='int', default=9042),
        username=dict(type='str'),
        password=dict(type='str', no_log=True),
        keyspace=dict(type='str'),
        file=dict(type='str'),
        execute=dict(type='str'),
        encoding=dict(type='str', default='utf-8'),
        cqlshrc=dict(type='str'),
        cqlversion=dict(type='str'),
        protocol_version=dict(type='str'),
        connect_timeout=dict(type='int'),
        request_timeout=dict(type='int'),
        tty=dict(type='bool', default=False),
        debug=dict(type='bool', default=False),
        ssl=dict(type='bool', default=False),
        no_compact=dict(type='bool', default=False),
        cqlsh_cmd=dict(type='str', default='cqlsh')
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    args = [
        module.params['cqlsh_cmd'],
        module.params['cqlsh_host'],
        module.params['cqlsh_port'],
    ]

    args = add_arg_to_cmd(args, "--username", module.params['username'])
    args = add_arg_to_cmd(args, "--password", module.params['password'])
    args = add_arg_to_cmd(args, "--keyspace", module.params['keyspace'])
    args = add_arg_to_cmd(args, "--file", module.params['file'])
    args = add_arg_to_cmd(args, "--execute", module.params['execute'])
    args = add_arg_to_cmd(args, "--encoding", module.params['encoding'])
    args = add_arg_to_cmd(args, "--cqlshrc", module.params['cqlshrc'])
    args = add_arg_to_cmd(args, "--protocol-version", module.params['protocol_version'])
    args = add_arg_to_cmd(args, "--connect-timeout", module.params['connect_timeout'])
    args = add_arg_to_cmd(args, "--request-timeout", module.params['request_timeout'])
    args = add_arg_to_cmd(args, "--tty", None, module.params['tty'])
    args = add_arg_to_cmd(args, "--debug", None, module.params['debug'])
    args = add_arg_to_cmd(args, "--no-compact", None, module.params['no_compact'])

    result = module.run_command(args, check_rc=True)
    module.exit_json(msg="I am exiting")
    # Everything is good
    module.exit_json(**result)


if __name__ == '__main__':
    main()
