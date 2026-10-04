from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

import pytest

from ansible_collections.community.cassandra.plugins.module_utils.nodetool_netstats import node_mode, parse_netstats

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


@pytest.mark.parametrize("mode", ["NORMAL", "LEAVING", "DECOMMISSIONED",
                                  "DECOMMISSION_FAILED", "JOINING"])
def test_node_mode(mode):
    assert node_mode("Mode: {0}\nNot sending any streams.\n".format(mode)) == mode


def test_node_mode_with_streams():
    assert node_mode(load_fixture("nodetool_netstats_joining.txt")) == "JOINING"


def test_node_mode_no_mode_line():
    assert node_mode("Not sending any streams.\n") is None


def test_node_mode_empty():
    assert node_mode("") is None


def test_normal_not_streaming():
    assert parse_netstats(load_fixture("nodetool_netstats_normal.txt")) == ("NORMAL", [])


def test_joining_streaming():
    mode, streams = parse_netstats(load_fixture("nodetool_netstats_joining.txt"))
    assert mode == "JOINING"
    assert streams == [
        "Bootstrap 9a3f2c10-6b1e-11ef-8b1a-3d7c1c0a1b2c",
        "    /10.0.0.1",
        "        Receiving 12 files, 104857600 bytes total. Already received 3 files (25.00%), "
        "26214400 bytes total (25.00%)",
        "            /var/lib/cassandra/data/ks/t-1/nb-1-big-Data.db 8738133/8738133 bytes (100%) "
        "received from idx:0/10.0.0.1",
    ]


def test_starting_no_statistics():
    # A node still starting prints no read repair or pool statistics.
    assert parse_netstats("Mode: STARTING\nNot sending any streams.\n") == ("STARTING", [])


def test_lines_before_mode_ignored():
    out = "WARN: a JVM warning\n" + load_fixture("nodetool_netstats_normal.txt")
    assert parse_netstats(out) == ("NORMAL", [])


def test_stops_at_pool_statistics():
    out = "Mode: NORMAL\nNot sending any streams.\nPool Name   Active   Pending\nLarge messages   n/a   0\n"
    assert parse_netstats(out) == ("NORMAL", [])


def test_node_down_output():
    assert parse_netstats("") == ("", [])
