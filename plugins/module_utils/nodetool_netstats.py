from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


def node_mode(netstats_out):
    """Return the mode from the "Mode: X" line of nodetool netstats, None if absent."""
    for line in netstats_out.splitlines():
        if line.startswith("Mode:"):
            return line.split(":", 1)[1].strip()
    return None


def parse_netstats(netstats_out):
    """mode ("" if absent), and the stream session lines between the mode line and the read repair statistics."""
    streams = []
    after_mode = False
    for line in netstats_out.splitlines():
        if line.startswith("Mode:"):
            after_mode = True
            continue
        if line.startswith(("Read Repair Statistics", "Pool Name")):
            break
        if after_mode and line.strip() and line.strip() != "Not sending any streams.":
            streams.append(line)
    return node_mode(netstats_out) or "", streams
