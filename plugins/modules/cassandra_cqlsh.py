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
    default: 5
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
  transform:
    description:
      - Transform the output returned to the user..
      - auto - Attempt to automatically decice the best tranformation.
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
      - Use by the split action in the transform stage.
    type: str
    default: " "
'''

EXAMPLES = '''
- name: Run the DESC KEYSPACES cql command
  community.cassandra.cassandra_cqlsh:
    execute: "DESC KEYSPACES"

- name: Run a file containing cql commands
  community.cassandra.cassandra_cqlsh:
    file: "/path/to/cql/file.sql"
'''

RETURN = '''
msg:
  description: A message indicating what has happened.
  returned: always
  type: str
transformed_output:
  description: Output from the cqlsh command. We attempt to parse this into a list or json where possible.
  returned: on success
  type: list
changed:
  description: Change status
  returned: alawys
  type: bool
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
        elif isinstance(output.strip().split(","), list):
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
        results = output.strip().split("\n")[2:-2]
        if len(results) > 0:
            for item in results:
                json_list.append(json.loads(item))
        output = json_list
    elif transform_type == "split":
        output = output.strip().split(split_char)
    elif tranform_type == "raw":
        output = output.strip()
    return output


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
        connect_timeout=dict(type='int', default=5),
        request_timeout=dict(type='int', default=10),
        tty=dict(type='bool', default=False),
        debug=dict(type='bool', default=False),
        ssl=dict(type='bool', default=False),
        no_compact=dict(type='bool', default=False),
        cqlsh_cmd=dict(type='str', default='cqlsh'),
        transform=dict(type='str', choices=["auto", "split", "json", "raw"], default="auto"),
        split_char=dict(type='str', default=" ")
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
    # module.exit_json(msg=str(args))

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = module.run_command(" ".join(str(item) for item in args), check_rc=False)
    if rc != 0:
        module.fail_json(msg=err.strip())
    else:
        result['changed'] = False
        try:
            output = transform_output(out,
                                      module.params['transform'],
                                      module.params['split_char'])
            result['transformed_output'] = output
            result['msg'] = "transform type was {0}".format(module.params['transform'])
        except Exception as excep:
            result['msg'] = "Error tranforming output: {0}".format(str(excep))
            result['transformed_output'] = None

    if module.params['debug']:
        result['out'] = out
        result['err'] = err
        result['rc'] = rc

    module.exit_json(**result)


if __name__ == '__main__':
    main()
