from __future__ import (absolute_import, division, print_function)
__metaclass__ = type
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
        self.nodetool_flags = module.params['nodetool_flags']
        self.debug = module.params['debug']
        if self.host is None:
            self.host = socket.getfqdn()

    def execute_command(self, cmd):
        return self.module.run_command(cmd)

    def nodetool_cmd(self, sub_command):
        if self.nodetool_path is not None and len(self.nodetool_path) > 0:
            if not self.nodetool_path.endswith('/'):  # replace with os.path.join
                self.nodetool_path += '/'
        else:
            self.nodetool_path = ""
        cmd = "{0}nodetool {1} --host {2} --port {3}".format(self.nodetool_path,
                                                             self.nodetool_flags,
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


class NodeToolCommandSimple(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;
        - run_command
    """

    def __init__(self, module, cmd):
        NodeToolCmd.__init__(self, module)
        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)


class NodeToolCommandKeyspaceTable(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;
        - run_command
    2020.01.10 - Added additonal keyspace and table params
    """

    def __init__(self, module, cmd):
        NodeToolCmd.__init__(self, module)
        self.keyspace = module.params['keyspace']
        self.table = module.params['table']
        if self.keyspace is not None:
            cmd = "{0} {1}".format(cmd, self.keyspace)
        if self.table is not None:
            if isinstance(self.table, str):
                cmd = "{0} {1}".format(cmd, self.table)
            elif isinstance(self.table, list):
                cmd = "{0} {1}".format(cmd, " ".join(self.table))
        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)


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


class NodeTool3PairCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;

        - status_command
        - enable_command
        - disable_command
    """

    def __init__(self, module, status_cmd, enable_cmd, disable_cmd):
        NodeToolCmd.__init__(self, module)
        self.status_cmd = status_cmd
        self.enable_cmd = enable_cmd
        self.disable_cmd = disable_cmd

    def status_command(self):
        return self.nodetool_cmd(self.status_cmd)

    def enable_command(self):
        return self.nodetool_cmd(self.enable_cmd)

    def disable_command(self):
        return self.nodetool_cmd(self.disable_cmd)


class NodeTool4PairCommand(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;

        - status_command
        - enable_command
        - disable_command
        - reset_command

    Additional args also added to enable command method
    """

    def __init__(self, module, status_cmd, enable_cmd, disable_cmd, reset_cmd, additional_args):
        NodeToolCmd.__init__(self, module)
        self.status_cmd = status_cmd
        self.enable_cmd = enable_cmd
        self.disable_cmd = disable_cmd
        self.reset_cmd = reset_cmd
        self.additional_args = additional_args

    def status_command(self):
        return self.nodetool_cmd(self.status_cmd)

    def enable_command(self):
        cmd = "{0} {1}".format(self.enable_cmd, self.additional_args)
        return self.nodetool_cmd(cmd)

    def disable_command(self):
        return self.nodetool_cmd(self.disable_cmd)

    def reset_command(self):
        return self.nodetool_cmd(self.reset_cmd)


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


class NodeToolCommandKeyspaceTableNumJobs(NodeToolCmd):

    """
    Inherits from the NodeToolCmd class. Adds the following methods;
        - run_command
    2020.01.10 - Added additonal keyspace and table params
    """

    def __init__(self, module, cmd):
        NodeToolCmd.__init__(self, module)
        self.keyspace = module.params['keyspace']
        self.table = module.params['table']
        self.num_jobs = module.params['num_jobs']
        cmd = "{0} -j {1}".format(cmd, self.num_jobs)
        if self.keyspace is not None:
            cmd = "{0} {1}".format(cmd, self.keyspace)
        if self.table is not None:
            if isinstance(self.table, str):
                cmd = "{0} {1}".format(cmd, self.table)
            elif isinstance(self.table, list):
                cmd = "{0} {1}".format(cmd, " ".join(self.table))
        self.cmd = cmd

    def run_command(self):
        return self.nodetool_cmd(self.cmd)
