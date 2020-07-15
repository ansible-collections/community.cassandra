from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


def cassandra_common_argument_spec():
    """
    Returns a dict containing common options for the Cassandra modules
    in this collection
    """
    return dict(
        debug=dict(type='bool', default=False, required=False),
        host=dict(type='str', default="127.0.0.1"),
        nodetool_path=dict(type='str', default=None, required=False),
        password=dict(type='str', no_log=True),
        password_file=dict(type='str', no_log=True),
        port=dict(type='int', default=7199),
        username=dict(type='str', no_log=True)
    )
