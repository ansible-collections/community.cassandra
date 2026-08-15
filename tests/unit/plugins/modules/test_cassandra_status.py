from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

import pytest

from ansible_collections.community.cassandra.plugins.modules.cassandra_status import (
    cluster_up_down,
    node_status_column_offsets,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


@pytest.fixture
def vnodes_status():
    return load_fixture("nodetool_status_vnodes.txt")


@pytest.fixture
def vnodes_freshly_joined_status():
    return load_fixture("nodetool_status_vnodes_freshly_joined.txt")


@pytest.fixture
def vnodes_load_unknown_status():
    return load_fixture("nodetool_status_vnodes_load_unknown.txt")


@pytest.fixture
def token_per_node_status():
    return load_fixture("nodetool_status_token_per_node.txt")


@pytest.fixture
def multi_dc_status():
    return load_fixture("nodetool_status_multi_dc.txt")


class TestNodeStatusColumnOffsets:

    def test_vnodes_header(self, vnodes_status):
        header = vnodes_status.splitlines()[4]
        offsets = node_status_column_offsets(header)
        assert offsets is not None
        # Tokens comes before Owns in vnodes mode
        assert offsets["tokens"] < offsets["owns"] < offsets["host_id"] < offsets["rack"]

    def test_legacy_token_per_node_header(self, token_per_node_status):
        header = token_per_node_status.splitlines()[4]
        offsets = node_status_column_offsets(header)
        assert offsets is not None
        # Owns/Host ID come before Token in legacy mode -- the opposite order
        assert offsets["owns"] < offsets["host_id"] < offsets["tokens"] < offsets["rack"]

    def test_unrecognised_header_returns_none(self):
        assert node_status_column_offsets("not a nodetool status header at all") is None


class TestClusterUpDown:

    def test_vnodes_normal(self, vnodes_status):
        dc = cluster_up_down(vnodes_status)["datacenter1"]
        assert dc["up"] == ["10.118.154.136"]
        assert dc["down"] == ["10.118.154.139"]
        assert dc["nodes"][0] == {
            "address": "10.118.154.136",
            "load": "287.59 KiB",
            "tokens": "16",
            "owns": "43.2%",
            "host_id": "ddlf3452-4c9d-47af-a7ed-94f78acd1c6d",
            "rack": "rack1",
            "status": "U",
            "state": "N",
        }

    def test_vnodes_freshly_joined_node_has_blank_tail(self, vnodes_freshly_joined_status):
        # Regression: a node that hasn't reported ownership/host_id/rack yet
        # (e.g. right after joining) used to make line.split() produce fewer
        # than 8 tokens, crashing fixed positional indexing with an
        # IndexError. Column-offset parsing must degrade gracefully instead.
        dc = cluster_up_down(vnodes_freshly_joined_status)["datacenter1"]
        assert "10.118.154.136" in dc["up"]
        assert "10.118.154.137" in dc["up"]
        joining_node = [n for n in dc["nodes"] if n["address"] == "10.118.154.137"][0]
        assert joining_node["tokens"] == "16"
        assert joining_node["owns"] == ""
        assert joining_node["host_id"] == ""
        assert joining_node["rack"] == ""

    def test_vnodes_load_unknown_does_not_shift_other_fields(self, vnodes_load_unknown_status):
        # Regression: nodetool prints Load as a single "?" token (instead of
        # the usual 2-token "648.19 GiB") while a node hasn't reported its
        # load yet. Fixed positional indexing from the left mis-assigned
        # every field after Load in that case; column-offset parsing doesn't,
        # since Load's width has no effect on where the other columns start.
        node = cluster_up_down(vnodes_load_unknown_status)["datacenter1"]["nodes"][0]
        assert node["load"] == "?"
        assert node["tokens"] == "16"
        assert node["owns"] == "43.2%"
        assert node["host_id"] == "ddlf3452-4c9d-47af-a7ed-94f78acd1c6d"
        assert node["rack"] == "rack1"

    def test_legacy_token_per_node_columns_are_not_swapped(self, token_per_node_status):
        # Regression: in "token-per-node" mode (no vnodes) nodetool prints
        # columns as Owns/Host ID/Token/Rack -- a different order to vnodes'
        # Tokens/Owns/Host ID/Rack. Code that assumes one fixed order silently
        # mislabels tokens/owns/host_id instead of crashing.
        dc = cluster_up_down(token_per_node_status)["datacenter1"]
        up_node, down_node = dc["nodes"]

        assert up_node["owns"] == "20.0%"
        assert up_node["host_id"] == "c0d8906d-8555-43b0-b104-cc9781349816"
        assert up_node["tokens"] == "842150494799422323"
        assert up_node["rack"] == "rack1"

        assert down_node["owns"] == "?"
        assert down_node["host_id"] == "d1e8906d-8555-43b0-b104-cc9781349817"
        assert down_node["tokens"] == "-9223372036854775808"
        assert down_node["rack"] == "rack2"

    def test_multiple_datacenters_recompute_offsets_independently(self, multi_dc_status):
        # A header (and its column order) is only valid for the datacenter
        # section it belongs to -- offsets must be re-derived per section,
        # not carried over from the previous one. Here dc1 is vnodes-style
        # and dc2 is legacy token-per-node-style, in the same output.
        result = cluster_up_down(multi_dc_status)

        dc1_node = result["datacenter1"]["nodes"][0]
        assert dc1_node["tokens"] == "16"
        assert dc1_node["owns"] == "50.0%"

        dc2_node = result["datacenter2"]["nodes"][0]
        assert dc2_node["tokens"] == "123456789"
        assert dc2_node["owns"] == "50.0%"

    def test_no_header_seen_yet_is_skipped_not_crashed(self):
        # A stray line matching the U/D status pattern before any column
        # header has been parsed must be skipped, not indexed blindly.
        stdout = "Datacenter: datacenter1\n===\nUN  looks like a node line but no header yet\n"
        result = cluster_up_down(stdout)
        assert result["datacenter1"]["nodes"] == []
