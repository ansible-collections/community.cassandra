#!/usr/bin/python

# 2021 Rhys Campbell <rhyscampbell@bluewin.ch>
# https://github.com/rhysmeister
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function


DOCUMENTATION = '''
---
module: cassandra_fullquerylog
author: Rhys Campbell (@rhysmeister)
short_description: "Manages the full query log feature."
requirements:
  - nodetool
description:
  - "Manages the full query log feature."
  - "Enable, disable or reset feature."
  - "Manage configuration."
  - "Supported from Cassandra 4.0 onwards."
  - "When state is disabled the value of the other configuration options are ignored."
  - "The module always returns changed when state is reset."

extends_documentation_fragment:
  - community.cassandra.nodetool_module_options

options:
  state:
    description:
      - The required status
    type: str
    choices:
      - enabled
      - disabled
      - reset
    default: enabled
  log_dir:
    description:
      - The log directory.
    type: str
    aliases:
      - path
  archive_command:
    description:
      - Command that will handle archiving rolled full query log files.
      - Format is "/path/to/script.sh %path" where %path will be replaced with the file to archive.
    type: str
  roll_cycle:
    description:
      - How often to roll the log file.
    type: str
    choices:
      - MINUTELY
      - HOURLY
      - DAILY
    default: HOURLY
  blocking:
    description:
      - If the queue is full whether to block producers or drop samples.
    type: bool
    default: yes
    aliases:
      - "block"
  max_log_size:
    description:
      - How many bytes of log data to store before dropping segments.
    type: int
    default: 17179869184
  max_queue_weight:
    description:
      - Maximum number of bytes of query data to queue to disk before blocking or dropping samples.
    type: int
    default: 268435456
  max_archive_retries:
    description:
      - Max number of archive retries.
    type: int
    default: 10
  debug:
    description:
      - Enable extra debug output.
    type: bool
    default: false
'''

EXAMPLES = '''
- name: Enable the full query log
  community.cassandra.cassandra_fullquerylog:
    state: enabled
    log_dir: /var/log/cassandra_log_archive

- name: Disable the full query log
  community.cassandra.cassandra_fullquerylog:
    state: disabled

- name: Enable the full query log and configure daily rollover & custom archiving script
  community.cassandra.cassandra_fullquerylog:
    state: enabled
    log_dir: /var/log/cassandra_log_archive
    roll_cyle: DAILY
    archive_command: "/path/to/script.sh %path"
'''

RETURN = '''
msg:
  description: A short description of what the module did.
  returned: always
  type: str
fullquerylog_config:
  description: The config of the full query log feature.
  returned: success
  type: dict
  sample: >
    { 'max_queue_weight': 268435456, 'max_log_size': 17179869184, 'enabled': True, 'roll_cycle': 'HOURLY',
      'archive_command': None, 'log_dir': None, 'max_archive_retries': 10, 'block': True}
'''

from ansible.module_utils.basic import AnsibleModule
import shlex
import pipes
__metaclass__ = type


from ansible_collections.community.cassandra.plugins.module_utils.nodetool_cmd_objects import NodeTool4PairCommand
from ansible_collections.community.cassandra.plugins.module_utils.cassandra_common_options import cassandra_common_argument_spec


def escape_param(param):
    '''
    Escapes the given parameter
    @param - The parameter to escape
    '''
    escaped = None
    if hasattr(shlex, 'quote'):
        escaped = shlex.quote(param)
    elif hasattr(pipes, 'quote'):
        escaped = pipes.quote(param)
    else:
        escaped = "'" + param.replace("'", "'\\''") + "'"
    return escaped


# TODO - This could go in a shared fucntion file and be unit tested
def parse_getfullquerylog(nodetool_output):
    """
    This function passed the output from nodetool getfullquerylog and
    returns it in a Python dictionary.
    i.e.
    enabled             false
    log_dir
    archive_command
    roll_cycle          HOURLY
    block               true
    max_log_size        17179869184
    max_queue_weight    268435456
    max_archive_retries 10

    Is transformed to...

    { 'max_queue_weight': 268435456,
      'max_log_size': 17179869184,
      'enabled': True,
      'roll_cycle': 'HOURLY',
      'archive_command': None,
      'log_dir': None,
      'max_archive_retries': 10,
      'block': True}

    """
    bool_list = ['enabled', 'block']
    int_list = ['max_log_size', 'max_queue_weight', 'max_archive_retries']
    d = dict()

    for line in nodetool_output.split('\n'):
        config_pair = line.split()
        if len(config_pair) > 0:
            if config_pair[0] in bool_list:
                cast_function = bool
            elif config_pair[0] in int_list:
                cast_function = int
            else:
                cast_function = str
            try:
                d[config_pair[0]] = cast_function(config_pair[1])
            except IndexError:
                d[config_pair[0]] = None
    return d


def fullqueryconfig_diff(config_dict, module):
    """
    Compare requested state from module with the actual config
    of the full query log
    """
    diff = False
    if config_dict['enabled'] != module.params['state']:
        diff = True
    myList = list(config_dict.keys())
    myList.remove('enabled')
    for k in myList:
        if k == 'block':
            if config_dict[k] == module.params['blocking']:
                diff = True
                break
        elif config_dict[k] != module.params[k]:
            diff = True
            break
    return diff


def main():
    argument_spec = cassandra_common_argument_spec()
    argument_spec.update(
        state=dict(type='str', choices=['enabled', 'disabled', 'reset'], default='enabled'),
        log_dir=dict(type='str', aliases=['path']),
        archive_command=dict(type='str'),
        roll_cycle=dict(type='str', choices=['MINUTELY', 'HOURLY', 'DAILY'], default='HOURLY'),
        blocking=dict(type='bool', default=True, aliases=['block']),
        max_log_size=dict(type='int', default=17179869184),
        max_queue_weight=dict(type='int', default=268435456),
        max_archive_retries=dict(type='int', default=10),
        debug=dict(type='bool', default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[("state", "enabled", ["log_dir"])]
    )

    status_cmd = 'getfullquerylog'
    enable_cmd = 'enablefullquerylog'
    disable_cmd = 'disablefullquerylog'
    reset_cmd = 'resetfullquerylog'

    archive_command = module.params['archive_command']
    additional_args = ""

    if module.params['state'] == "enabled":
        if archive_command is not None:
            additional_args = "--archive-command \"{0}\"".format(escape_param(archive_command))
        additional_args += " --blocking {0}".format(str(module.params['blocking']))
        additional_args += " --max-archive-retries {0}".format(module.params['max_archive_retries'])
        additional_args += " --max-log-size {0}".format(module.params['max_log_size'])
        additional_args += " --max-queue-weight {0}".format(module.params['max_queue_weight'])
        additional_args += " --roll-cycle {0}".format(module.params['roll_cycle'])
        additional_args += " --path {0}".format(escape_param(module.params['log_dir']))

    n = NodeTool4PairCommand(module,
                             status_cmd,
                             enable_cmd,
                             disable_cmd,
                             reset_cmd,
                             additional_args)

    rc = None
    out = ''
    err = ''
    result = {}

    (rc, out, err) = n.status_command()
    # Parse the output into a dict
    out = out.strip()
    fullquerylog_config = parse_getfullquerylog(out)
    if module.params['debug']:
        if out:
            result['stdout'] = out
        if err:
            result['stderr'] = err
        result['additional_args'] = additional_args

    if module.params['state'] == "disabled":

        if rc != 0:
            module.fail_json(name=status_cmd,
                             msg="status command failed", **result)
        if module.check_mode:
            if fullqueryconfig_diff(fullquerylog_config, module):
                result['changed'] = True
                result['msg'] = "check mode"
                result['fullquerylog_config'] = fullquerylog_config
            else:
                result['changed'] = False
                result['msg'] = "check mode"
                result['fullquerylog_config'] = fullquerylog_config
        if fullquerylog_config['enabled']:
            (rc, out, err) = n.disable_command()
            if module.params['debug']:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
        if rc != 0:
            module.fail_json(name=disable_cmd,
                             msg="disable command failed", **result)
        else:
            result['changed'] = True
            result['msg'] = "fullquerylog disabled"
            result['fullquerylog_config'] = fullquerylog_config

    elif module.params['state'] == "enabled":

        if rc != 0:
            module.fail_json(name=status_cmd,
                             msg="status command failed", **result)
        if module.check_mode:
            if fullqueryconfig_diff(fullquerylog_config, module):
                result['changed'] = True
                result['msg'] = "check mode"
                result['fullquerylog_config'] = fullquerylog_config
            else:
                result['changed'] = False
                result['msg'] = "check mode"
                result['fullquerylog_config'] = fullquerylog_config
        else:
            if fullqueryconfig_diff(fullquerylog_config, module):
                (rc, out, err) = n.enable_command()
                if module.params['debug']:
                    if out:
                        result['stdout'] = out
                    if err:
                        result['stderr'] = err
                if rc is not None and rc != 0:
                    module.fail_json(name=enable_cmd,
                                     msg="enable command failed", **result)
                result['changed'] = True
                result['msg'] = 'fullquerylog reconfigured'
                result['fullquerylog_config'] = fullquerylog_config
            else:
                result['changed'] = False
                result['msg'] = 'fullquerylog state unchanged'
                result['fullquerylog_config'] = fullquerylog_config
    elif module.params['state'] == "reset":
        if rc != 0:
            module.fail_json(name=reset_cmd,
                             msg="resetfullquerylog command failed", **result)
        if module.check_mode:
            module.exit_json(changed=True, msg="resetfullquerylog succeeded check mode", **result)
        else:
            (rc, out, err) = n.reset_command()
            if module.params['debug']:
                if out:
                    result['stdout'] = out
                if err:
                    result['stderr'] = err
            if rc is not None and rc != 0:
                module.fail_json(name=reset_cmd,
                                 msg="resetfullquerylog command failed", **result)
            else:
                result['changed'] = True
                result['msg'] = 'resetfullquerylog succeeded'
                result['fullquerylog_config'] = fullquerylog_config

    module.exit_json(**result)


if __name__ == '__main__':
    main()
