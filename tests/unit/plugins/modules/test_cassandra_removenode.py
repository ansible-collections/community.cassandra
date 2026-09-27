from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

import pytest

from ansible_collections.community.cassandra.plugins.modules import cassandra_removenode
from ansible_collections.community.cassandra.plugins.modules.cassandra_removenode import (
    leaving_nodes,
    node_state,
    removenode_cmd,
    valid_uuid,
)

from unittest.mock import patch

HOST_ID = "2d29b2bc-faa5-4837-935c-41c3945119e2"
OTHER_ID = "e6097511-4383-4e46-a60f-01d560fbfb57"

STATUS = """Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address         Load        Tokens  Owns (effective)  Host ID                               Rack
UN  10.118.154.136  287.59 KiB  16      43.2%             ddf13452-4c9d-47af-a7ed-94f78acd1c6d  rack1
{state}  10.118.154.139  222.39 KiB  16      38.1%             {host_id}  rack1
"""


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
MULTI_DC_ID = "bbbbbbbb-2222-2222-2222-222222222222"


def single_dc(state, host_id=HOST_ID):
    return STATUS.format(state=state, host_id=host_id)


def multi_dc(state, host_id=HOST_ID):
    """Multi-DC fixture with the datacenter2 node set to state and host_id."""
    with open(os.path.join(FIXTURES_DIR, "nodetool_status_multi_dc.txt")) as f:
        out = f.read()
    return out.replace("UN  10.0.1.1", state + "  10.0.1.1").replace(MULTI_DC_ID, host_id)


def other_node(status_out, state):
    """Set the state of the other node (the first UN line, in datacenter1)."""
    return status_out.replace("\nUN  ", "\n" + state + "  ", 1)


OTHER_IDS = {single_dc: "ddf13452-4c9d-47af-a7ed-94f78acd1c6d",
             multi_dc: "aaaaaaaa-1111-1111-1111-111111111111"}


@pytest.fixture(params=[single_dc, multi_dc], ids=["single_dc", "multi_dc"])
def status_with(request):
    return request.param


class ExitJson(Exception):
    pass


class FailJson(Exception):
    pass


class FakeModule:

    def __init__(self, argument_spec=None, supports_check_mode=False):
        self.params = dict(FakeModule.params)
        self.check_mode = self.params.pop('_check_mode', False)

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise FailJson(kwargs)


def run_main(status_out, force=False, check_mode=False, status_rc=0, removenode_rc=0,
             host_id=HOST_ID):
    """Run main() with nodetool mocked; return (exception, list of nodetool sub-commands)."""
    FakeModule.params = {'host_id': host_id, 'force': force, 'debug': False,
                         '_check_mode': check_mode}
    commands = []

    class FakeNodeTool:

        def __init__(self, module, cmd):
            self.cmd = cmd

        def run_command(self):
            commands.append(self.cmd)
            if self.cmd == "status":
                return status_rc, status_out, ''
            return removenode_rc, '', ''

    with patch.object(cassandra_removenode, 'AnsibleModule', FakeModule), \
            patch.object(cassandra_removenode, 'NodeToolCommandSimple', FakeNodeTool):
        with pytest.raises((ExitJson, FailJson)) as exc:
            cassandra_removenode.main()
    return exc.value, commands


class TestRemovenodeCmd:

    def test_remove_by_host_id(self):
        assert removenode_cmd(HOST_ID, False) == "removenode -- {0}".format(HOST_ID)

    def test_force_takes_no_host_id(self):
        assert removenode_cmd(HOST_ID, True) == "removenode force"


class TestValidUuid:

    def test_valid(self):
        assert valid_uuid(HOST_ID)

    @pytest.mark.parametrize("value", [HOST_ID + "x", HOST_ID + " ", "x" + HOST_ID, "XXXXXXXXXXXXXX"])
    def test_invalid(self, value):
        assert not valid_uuid(value)


class TestNodeState:

    @pytest.mark.parametrize("state", ["UN", "DN", "UL", "DL", "UJ", "?N", "?L"])
    def test_state(self, status_with, state):
        assert node_state(status_with(state), HOST_ID) == state

    def test_absent(self, status_with):
        assert node_state(status_with("DN", OTHER_ID), HOST_ID) is None


class TestLeavingNodes:

    def test_none(self, status_with):
        assert leaving_nodes(status_with("UN")) == []

    @pytest.mark.parametrize("state", ["UL", "DL", "?L"])
    def test_leaving(self, status_with, state):
        assert leaving_nodes(status_with(state)) == [HOST_ID]

    def test_both(self, status_with):
        out = other_node(status_with("DL"), "UL")
        assert leaving_nodes(out) == [OTHER_IDS[status_with], HOST_ID]


class TestMainForce:

    def test_dead_leaving_runs_force(self, status_with):
        res, commands = run_main(status_with("DL"), force=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "removenode force"]

    def test_absent_is_unchanged(self, status_with):
        res, commands = run_main(status_with("DN", OTHER_ID), force=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == "host_id does not exist in the cluster"
        assert commands == ["status"]

    def test_absent_with_other_leaving_is_unchanged(self, status_with):
        res, commands = run_main(other_node(status_with("DN", OTHER_ID), "UL"), force=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == "host_id does not exist in the cluster"
        assert commands == ["status"]

    def test_live_leaving_is_refused(self, status_with):
        res, commands = run_main(status_with("UL"), force=True)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == ("{0} is UL: a live node leaving (decommission), "
                                      "not a removal; nothing forced".format(HOST_ID))
        assert commands == ["status"]

    def test_dead_not_removed_fails(self, status_with):
        res, commands = run_main(status_with("DN"), force=True)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == \
            "no removal of {0} in progress: run it without force first".format(HOST_ID)
        assert commands == ["status"]

    @pytest.mark.parametrize("state", ["UN", "UJ", "UM"])
    def test_live_not_leaving_fails(self, status_with, state):
        res, commands = run_main(status_with(state), force=True)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == \
            "{0} is {1}, not a removal in progress; nothing forced".format(HOST_ID, state)
        assert commands == ["status"]

    def test_check_mode_does_not_run(self, status_with):
        res, commands = run_main(status_with("DL"), force=True, check_mode=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == "removenode command succeeded"
        assert commands == ["status"]

    @pytest.mark.parametrize("state", ["UL", "DL", "?L"])
    def test_other_leaving_is_refused(self, status_with, state):
        res, commands = run_main(other_node(status_with("DL"), state), force=True)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == (
            "other nodes are leaving ({0}): removenode force would force them too; "
            "nothing forced".format(OTHER_IDS[status_with]))
        assert commands == ["status"]

    def test_other_leaving_is_refused_in_check_mode(self, status_with):
        res, commands = run_main(other_node(status_with("DL"), "UL"), force=True,
                                 check_mode=True)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == (
            "other nodes are leaving ({0}): removenode force would force them too; "
            "nothing forced".format(OTHER_IDS[status_with]))
        assert commands == ["status"]

    def test_other_normal_nodes_run_force(self, status_with):
        res, commands = run_main(other_node(status_with("DL"), "DN"), force=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == "removenode command succeeded"
        assert commands == ["status", "removenode force"]

    def test_force_failure(self, status_with):
        res, commands = run_main(status_with("DL"), force=True, removenode_rc=1)
        assert isinstance(res, FailJson)
        assert res.args[0]['rc'] == 1
        assert res.args[0]['msg'] == "removenode command failed"
        assert commands == ["status", "removenode force"]


class TestMainRemove:

    def test_other_leaving_does_not_block_removal(self, status_with):
        res, commands = run_main(other_node(status_with("DN"), "UL"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == "removenode command succeeded"
        assert commands == ["status", "removenode -- {0}".format(HOST_ID)]

    def test_unknown_status_runs_removenode(self, status_with):
        res, commands = run_main(status_with("?N"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "removenode -- {0}".format(HOST_ID)]

    def test_present_runs_removenode(self, status_with):
        res, commands = run_main(status_with("DN"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "removenode -- {0}".format(HOST_ID)]

    def test_absent_is_unchanged(self, status_with):
        res, commands = run_main(status_with("DN", OTHER_ID))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == "host_id does not exist in the cluster"
        assert commands == ["status"]

    def test_check_mode_does_not_run(self, status_with):
        res, commands = run_main(status_with("DN"), check_mode=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == "removenode command succeeded"
        assert commands == ["status"]

    def test_host_id_trailing_space_is_stripped(self, status_with):
        res, commands = run_main(status_with("DN"), host_id=HOST_ID + " ")
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "removenode -- {0}".format(HOST_ID)]

    def test_host_id_uppercase_is_lowercased(self, status_with):
        res, commands = run_main(status_with("DN"), host_id=HOST_ID.upper())
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "removenode -- {0}".format(HOST_ID)]

    def test_host_id_trailing_text_fails(self, status_with):
        res, commands = run_main(status_with("DN"), host_id=HOST_ID + "x")
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == "host_id is not a valid uuid"
        assert commands == []

    def test_status_failure(self):
        res, commands = run_main('', status_rc=1)
        assert isinstance(res, FailJson)
        assert res.args[0]['rc'] == 1
        assert res.args[0]['msg'] == "removenode command failed"
        assert commands == ["status"]
