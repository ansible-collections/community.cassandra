#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_concurrency
author: Rhys Campbell (@rhysmeister)
short_description: Manage concurrency parameters on the Cassandra node.
requirements: [ nodetool ]
description:
    - Manage concurrency parameters on the Cassandra node.
    - Set maximum concurrency for processing stage.
    - Set number of concurrent compactors.
    - Set the number of concurrent view builders in the system.

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  concurrency_type:
    description:
      - Type of concurrency to manage.
    type: str
    choices:
      - "default"
      - "compactors"
      - "viewbuilders"
    default: "default"
  concurrency_stage:
    description:
      - The processing stage
      - Only relevent when concurrency_type is default
    type: str
    choices:
      - "AntiEntropyStage"
      - "CounterMutationStage"
      - "GossipStage"
      - "ImmediateStage"
      - "InternalResponseStage"
      - "MigrationStage"
      - "MiscStage"
      - "MutationStage"
      - "ReadStage"
      - "RequestResponseStage"
      - "TracingStage"
      - "ViewMutationStage"
  value:
    description:
      - Number of threads / maximum concurrency.
    type: int
    required: True
'''

EXAMPLES = '''
- name: Set concurrency for read processing stage
  community.cassandra.cassandra_concurrency:
    concurrency_stage: "ReadStage"
    value: 8

- name: Set concurrency for compactors
  community.cassandra.cassandra_concurrency:
    concurrency_type: "compactors"
    value: 2

- name: Set concurrency for view builders
  community.cassandra.cassandra_concurrency:
    concurrency_type: "viewbuilders"
    value: 1
'''

RETURN = '''
msg:
  description: A brief description of what happened.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeToolGetSetCommand
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def main():

    cs_choices = [
        "AntiEntropyStage",
        "CounterMutationStage",
        "GossipStage",
        "ImmediateStage",
        "InternalResponseStage",
        "MigrationStage",
        "MiscStage",
        "MutationStage",
        "ReadStage",
        "RequestResponseStage",
        "TracingStage",
        "ViewMutationStage"
    ]

    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        concurrency_type=dict(type='str', choices=["default", "compactors", "viewbuilders"], default="default"),
        concurrency_stage=dict(type='str', choices=cs_choices),
        value=dict(type='int', required=True)
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[["concurrency_type", "default", ["concurrency_stage"]]]
    )

    concurrency_type = module.params['concurrency_type']
    concurrency_stage = module.params['concurrency_stage']
    value = module.params['value']

    if concurrency_type != "default":
        get_cmd = "{0}{1}".format("getconcurrent", concurrency_type)
        set_cmd = "{0}{1} -- {2}".format("setconcurrent", concurrency_type, value)
    else:
        get_cmd = "{0} -- {1} ".format("getconcurrency", concurrency_stage)
        set_cmd = "{0} -- {1} {2}".format("setconcurrency", concurrency_stage, value)

    n = NodeToolGetSetCommand(module, get_cmd, set_cmd)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.get_command()
    out = out.strip()

    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err

    # Matches the last int in the output
    try:
        current_value = out.split()[-1:][0]
        if current_value.isdigit():
            current_value = int(current_value)
        else:
            raise IndexError
    except IndexError as ie:
        module.fail_json(msg="Failure parsing {0} output: {1}".format(get_cmd, str(ie)), **result)

    if current_value == value:
        if rc != 0:  # should probably move this above
            result['changed'] = False
            module.fail_json(name=get_cmd,
                             msg="get command failed", **result)
        result['msg'] = "Configured value is already {0}".format(value)
    else:
        if module.check_mode:
            result['changed'] = True
            if concurrency_type != "default":
                result['msg'] = "{0} updated to {1}".format(concurrency_type, value)
            else:
                result['msg'] = "{0}/{1} updated to {2}".format(concurrency_type, concurrency_stage, value)
        else:
            (rc, out, err) = n.set_command()
            out = out.strip()
            if module.params['debug']:
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
                if concurrency_type != "default":
                    result['msg'] = "{0} updated to {1}".format(concurrency_type, value)
                else:
                    result['msg'] = "{0}/{1} updated to {2}".format(concurrency_type, concurrency_stage, value)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
