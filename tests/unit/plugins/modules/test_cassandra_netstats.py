from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

from ansible_collections.community.cassandra.plugins.modules.cassandra_netstats import parse_netstats

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


def test_normal_not_streaming():
    assert parse_netstats(load_fixture("nodetool_netstats_normal.txt")) == ("NORMAL", [])


def test_joining_streaming():
    mode, streams = parse_netstats(load_fixture("nodetool_netstats_joining.txt"))
    assert mode == "JOINING"
    assert streams[0].startswith("Bootstrap ")
    assert len(streams) == 4


def test_node_down_output():
    assert parse_netstats("") == ("", [])
