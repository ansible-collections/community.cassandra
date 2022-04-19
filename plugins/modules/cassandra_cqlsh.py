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
requirements:
  - cqlsh
description:
    - Run cql commands via the clqsh shell.
    - Run commands inline or using a cql file.
    - Attempts to parse returned data into a format that Ansible can use.
options:
  cqlsh_host:
    description:
      - Host to connect to
    type: str
    default: localhost
    aliases:
      - "login_host"
  cqlsh_port:
    description:
      - Port to connect to.
    type: int
    default: 9042
    aliases:
      - "login_port"
  username:
    description:
      - The C* user to authenticate with.
    type: str
    aliases:
      - "login_user"
  password:
    description:
      - The C* users password.
    type: str
    aliases:
      - "login_password"
  keyspace:
    description:
      - Authenticate to the given keyspace.
    type: str
  file:
    description:
      - Path to a file containing cql commands.
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
    default: 5
  request_timeout:
    description:
      - Specify the default request timeout in seconds.
    type: int
    default: 10
  tty:
    description:
      - Force tty mode.
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
      - cqlsh executable.
    type: str
    default: "cqlsh"
  transform:
    description:
      - Transform the output returned to the user.
      - auto - Attempt to automatically decide the best tranformation.
      - split - Split output on a character.
      - json - parse as json.
      - raw - Return the raw output.
    type: str
    choices:
      - "auto"
      - "split"
      - "json"
      - "raw"
    default: "auto"
  split_char:
    description:
      - Used by the split action in the transform stage.
    type: str
    default: " "
  additional_args:
    description:
      - Additional arguments to supply to the mongo command.
      - Supply as key-value pairs.
      - If the parameter is a valueless flag supply a bool value.
    type: raw
'''

EXAMPLES = '''
- name: Run the DESC KEYSPACES cql command
  community.cassandra.cassandra_cqlsh:
    execute: "DESC KEYSPACES"

- name: Run a file containing cql commands
  community.cassandra.cassandra_cqlsh:
    file: "/path/to/cql/file.sql"

- name: Run a cql query returning json data
  community.cassandra.cassandra_cqlsh:
    execute: "SELECT json * FROM my_keyspace.my_table WHERE partition = 'key' LIMIT 10"

- name: Use a different python
  community.cassandra.cassandra_cqlsh:
    execute: "SELECT json * FROM my_keyspace.my_table WHERE partition = 'key' LIMIT 10"
    additional_args:
      python: /usr/bin/python2
'''

RETURN = '''
file:
  description: CQL file that was executed successfully.
  returned: When a cql file is used.
  type: str
msg:
  description: A message indicating what has happened.
  returned: always
  type: str
transformed_output:
  description: Output from the cqlsh command. We attempt to parse this into a list or json where possible.
  returned: on success
  type: list
changed:
  description: Change status.
  returned: always
  type: bool
failed:
  description: Something went wrong.
  returned: on failure
  type: bool
out:
  description: Raw stdout from cqlsh.
  returned: when debug is set to true
  type: str
err:
  description: Raw stderr from cqlsh.
  returned: when debug is set to true
  type: str
rc:
  description: Return code from cqlsh.
  returned: when debug is set to true
  type: int
'''

from ansible.module_utils.basic import AnsibleModule, load_platform_subclass
import socket
import re
import time
import json
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
        if param_name == "--execute":
            if "'" in param_value:
                cmd_list.append('"{0}"'.format(param_value))
            else:
                cmd_list.append("'{0}'".format(param_value))
        else:
            cmd_list.append(param_value)
    elif is_bool is True:
        cmd_list.append(param_name)
    return cmd_list


def transform_output(output, transform_type, split_char):
    if transform_type == "auto":  # determine what transform_type to perform
        if output.strip().startswith("[json]"):
            transform_type = "json"
        elif isinstance(output.strip().split(None), list):  # Splits on whitespace
            transform_type = "split"
            split_char = None
        elif isinstance(output.strip().split(","), list):
            transform_type = "split"
            split_char = ","
        elif isinstance(output.strip().split(" "), list):
            transform_type = "split"
            split_char = " "
        elif isinstance(output.strip().split("|"), list):
            transform_type = "split"
            split_char = "|"
        elif isinstance(output.strip().split("\t"), list):
            transform_type = "split"
            split_char = "\t"
        else:
            tranform_type = "raw"
    if transform_type == "json":
        json_list = []
        if output.strip().split("\n")[-1] == "(0 rows)":
            output = json_list
        else:
            results = output.strip().split("\n")[2:-2]
            if len(results) > 0:
                for item in results:
                    json_list.append(json.loads(item))
            output = json_list
    elif transform_type == "split":
        output = output.strip().split(split_char)
    elif transform_type == "raw":
        output = output.strip()
    return output


def main():
    argument_spec = dict(
        cqlsh_host=dict(type='str', default='localhost', aliases=['login_host']),
        cqlsh_port=dict(type='int', default=9042, aliases=['login_port']),
        username=dict(type='str', aliases=['login_user']),
        password=dict(type='str', no_log=True, aliases=['login_password']),
        keyspace=dict(type='str', no_log=False),
        file=dict(type='str'),
        execute=dict(type='str'),
        encoding=dict(type='str', default='utf-8'),
        cqlshrc=dict(type='str'),
        cqlversion=dict(type='str'),
        protocol_version=dict(type='str'),
        connect_timeout=dict(type='int', default=5),
        request_timeout=dict(type='int', default=10),
        tty=dict(type='bool', default=False),
        debug=dict(type='bool', default=False),
        ssl=dict(type='bool', default=False),
        no_compact=dict(type='bool', default=False),
        cqlsh_cmd=dict(type='str', default='cqlsh'),
        transform=dict(type='str', choices=["auto", "split", "json", "raw"], default="auto"),
        split_char=dict(type='str', default=" "),
        additional_args=dict(type='raw')
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
    args = add_arg_to_cmd(args, "--ssl", None, module.params['ssl'])

    additional_args = module.params['additional_args']
    if additional_args is not None:
        for key, value in additional_args.items():
            if isinstance(value, bool):
                args.append(" --{0}".format(key))
            elif isinstance(value, str) or isinstance(value, int):
                args.append(" --{0} {1}".format(key, value))

    rc = None
    out = ''
    err = ''
    result = {}
    cmd = " ".join(str(item) for item in args)

    (rc, out, err) = module.run_command(cmd, check_rc=False)

    if module.params['debug']:
        result['out'] = out
        result['err'] = err
        result['rc'] = rc
        result['cmd'] = cmd

    if rc != 0:
        module.fail_json(msg="module execution failed", **result)
    else:
        result['changed'] = True
        try:
            output = transform_output(out,
                                      module.params['transform'],
                                      module.params['split_char'])
            result['transformed_output'] = output
            result['msg'] = "transform type was {0}".format(module.params['transform'])
            if module.params['file'] is not None:
                result['file'] = module.params['file']
        except Exception as excep:
            result['msg'] = "Error tranforming output: {0}".format(str(excep))
            result['transformed_output'] = None

    module.exit_json(**result)


if __name__ == '__main__':
    main()
