from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


def cassandra_common_argument_spec():
    """
    Returns a dict containing common options for the Cassandra modules
    in this collection
    """
    return dict(
        debug=dict(type='bool', default=False),
        host=dict(type='str', default="127.0.0.1", aliases=['login_host']),
        nodetool_path=dict(type='str', default=None),
        password=dict(type='str', no_log=True, aliases=['login_password']),
        password_file=dict(type='str', no_log=True, aliases=['login_password_file']),
        port=dict(type='int', default=7199, aliases=['login_port']),
        username=dict(type='str', no_log=True, aliases=['login_user']),
        nodetool_flags=dict(type='str', default="-Dcom.sun.jndi.rmiURLParsing=legacy"),
    )
