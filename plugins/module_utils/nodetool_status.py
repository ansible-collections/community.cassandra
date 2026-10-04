from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re


# A node line of nodetool status: status (U, D or ?) and state (N, L, J, M)
NODE_RE = re.compile(r'^[UD?][NLJM]\s+')


def address_part(address):
    """Return address without the port printed by nodetool -pp
    (10.0.0.1:7000, [::1]:7000)."""
    if address.startswith('['):
        return address[1:].partition(']')[0]
    if address.count(':') == 1:
        return address.partition(':')[0]
    return address


def ring_state(status_out, ip_address):
    """Return the status and state (UN, DN...) of ip_address in nodetool
    status output, or None when it is not in the ring."""
    for line in status_out.splitlines():
        if NODE_RE.match(line) and address_part(line.split()[1]) == ip_address:
            return line[:2]
    return None


def node_state(status_out, host_id):
    """Return the status and state (UN, DL...) of host_id in nodetool status
    output, or None when host_id is not in the ring."""
    for line in status_out.splitlines():
        if NODE_RE.match(line) and host_id in line.split():
            return line[:2]
    return None


def gossip_status(gossipinfo_out, ip_address):
    """Return the gossip STATUS (NORMAL, shutdown, LEFT...) of ip_address in
    nodetool gossipinfo output, '' when it has none, or None when the endpoint
    is unknown to gossip."""
    found = False
    status = ''
    for line in gossipinfo_out.splitlines():
        if not line.startswith(' '):  # endpoint header: /10.0.0.1 or host/10.0.0.1
            if found:
                break
            found = address_part(line.strip().rsplit('/', 1)[-1]) == ip_address
        elif found:
            key, dummy, value = line.strip().partition(':')
            if key == 'STATUS_WITH_PORT' or (key == 'STATUS' and not status):
                # STATUS:<version>:<status>,<details>
                status = value.partition(':')[2].split(',')[0]
    return status if found else None
