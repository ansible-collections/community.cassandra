from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


class ModuleDocFragment(object):
    # Standard documentation
    DOCUMENTATION = r'''
options:
  host:
    description:
      - The hostname.
    type: str
    default: 127.0.0.1
    aliases:
      - "login_host"
  port:
    description:
      - The Cassandra TCP port.
    type: int
    default: 7199
    aliases:
      - "login_port"
  password:
    description:
      - The password to authenticate with.
    type: str
    aliases:
      - "login_password"
  password_file:
    description:
      - Path to a file containing the password.
    type: str
    aliases:
      - "login_password_file"
  username:
    description:
      - The username to authenticate with.
    type: str
    aliases:
      - "login_user"
  nodetool_path:
    description:
      - The path to nodetool.
    type: str
  nodetool_flags:
    description:
      - Flags to pass to nodetool.
    type: str
    default: -Dcom.sun.jndi.rmiURLParsing=legacy
  debug:
    description:
      - Enable additional debug output.
    type: bool
    default: False
'''
