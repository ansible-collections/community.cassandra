from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from ansible_collections.community.cassandra.plugins.modules import cassandra_assassinate
from ansible_collections.community.cassandra.plugins.modules.cassandra_assassinate import (
    address_part,
    gossip_status,
    ring_state,
)

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

IP = "10.100.100.139"

STATUS = """Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address         Load        Tokens  Owns (effective)  Host ID                               Rack
UN  10.100.100.136  287.59 KiB  16      43.2%             ddf13452-4c9d-47af-a7ed-94f78acd1c6d  rack1
{state}  {ip}  222.39 KiB  16      38.1%             2d29b2bc-faa5-4837-935c-41c3945119e2  rack1
"""

GOSSIPINFO = """/10.100.100.136
  generation:1727500000
  heartbeat:5321
  STATUS:21:NORMAL,-9223372036854775808
  LOAD:5300:297433.0
  DC:9:datacenter1
  RACK:11:rack1
  HOST_ID:3:ddf13452-4c9d-47af-a7ed-94f78acd1c6d
  NATIVE_ADDRESS_AND_PORT:4:10.100.100.136:9042
  STATUS_WITH_PORT:20:NORMAL,-9223372036854775808
  TOKENS:19:<hidden>
{header}
  generation:1727400000
  heartbeat:9999
{states}  RACK:11:rack1
  TOKENS: not present
"""


def status(state, ip=IP):
    return STATUS.format(state=state, ip=ip)


def gossipinfo(gossip_state, header="/" + IP):
    """gossipinfo with IP in gossip_state; '' for an endpoint with no STATUS."""
    states = ""
    if gossip_state:
        states = ("  STATUS:40:{0},-4611686018427387904,1727800000000\n"
                  "  STATUS_WITH_PORT:39:{0},-4611686018427387904,1727800000000\n"
                  .format(gossip_state))
    return GOSSIPINFO.format(header=header, states=states)


GOSSIP_UNKNOWN = GOSSIPINFO.partition("{header}")[0]


class ExitJson(Exception):
    pass


class FailJson(Exception):
    pass


class FakeModule(object):

    def __init__(self, argument_spec=None, supports_check_mode=False):
        self.params = dict(FakeModule.params)
        self.check_mode = self.params.pop('_check_mode', False)

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise FailJson(kwargs)


def run_main(status_out, gossip_out=GOSSIP_UNKNOWN, ip_address=IP, check_mode=False,
             rcs=None, debug=False, assassinate_out=''):
    """Run main() with nodetool mocked; return (exception, list of nodetool sub-commands).
    rcs maps a sub-command (status, gossipinfo, assassinate) to its return code."""
    FakeModule.params = {'ip_address': ip_address, 'debug': debug, '_check_mode': check_mode}
    rcs = rcs or {}
    commands = []

    class FakeNodeTool(object):

        def __init__(self, module, cmd):
            self.cmd = cmd

        def run_command(self):
            commands.append(self.cmd)
            what = self.cmd.split()[0]
            out = {'status': status_out, 'gossipinfo': gossip_out}.get(what, assassinate_out)
            rc = rcs.get(what, 0)
            return rc, out, 'error' if rc else ''

    with patch.object(cassandra_assassinate, 'AnsibleModule', FakeModule), \
            patch.object(cassandra_assassinate, 'NodeToolCommandSimple', FakeNodeTool):
        with pytest.raises((ExitJson, FailJson)) as exc:
            cassandra_assassinate.main()
    return exc.value, commands


ASSASSINATE = "assassinate -- {0}".format(IP)
DONE = "nodetool assassinate executed successfully for endpoint: {0}".format(IP)
ABSENT = "{0} is not in the cluster".format(IP)


class TestAddressPart:

    @pytest.mark.parametrize("value, address", [
        ("10.0.0.1", "10.0.0.1"),
        ("10.0.0.1:7000", "10.0.0.1"),
        ("::1", "::1"),
        ("[::1]:7000", "::1"),
    ])
    def test_port_is_dropped(self, value, address):
        assert address_part(value) == address


class TestRingState:

    @pytest.mark.parametrize("state", ["UN", "UJ", "UL", "UM", "DN", "DL", "?N"])
    def test_state(self, state):
        assert ring_state(status(state), IP) == state

    def test_absent(self):
        assert ring_state(status("DN", ip="10.100.100.13"), IP) is None

    def test_address_prefix_does_not_match(self):
        assert ring_state(status("DN"), "10.100.100.13") is None

    def test_ipv6(self):
        assert ring_state(status("DN", ip="0:0:0:0:0:0:0:2"), "0:0:0:0:0:0:0:2") == "DN"

    @pytest.mark.parametrize("ip, wanted", [(IP + ":7000", IP),
                                            ("[0:0:0:0:0:0:0:2]:7000", "0:0:0:0:0:0:0:2")])
    def test_print_port(self, ip, wanted):
        # nodetool -pp
        assert ring_state(status("DN", ip=ip), wanted) == "DN"


class TestGossipStatus:

    @pytest.mark.parametrize("gossip_state", ["NORMAL", "shutdown", "LEFT", "removed"])
    def test_status(self, gossip_state):
        assert gossip_status(gossipinfo(gossip_state), IP) == gossip_state

    def test_unknown(self):
        assert gossip_status(GOSSIP_UNKNOWN, IP) is None

    def test_print_port_in_header(self):
        # nodetool -pp
        assert gossip_status(gossipinfo("shutdown", header="/" + IP + ":7000"), IP) == "shutdown"

    def test_print_port_in_ipv6_header(self):
        # nodetool -pp
        assert gossip_status(gossipinfo("shutdown", header="/[0:0:0:0:0:0:0:2]:7000"),
                             "0:0:0:0:0:0:0:2") == "shutdown"

    def test_status_only(self):
        # before STATUS_WITH_PORT (3.11)
        out = gossipinfo("").replace("  RACK:11:rack1\n  TOKENS: not",
                                     "  STATUS:40:LEFT,1,2\n  RACK:11:rack1\n  TOKENS: not")
        assert gossip_status(out, IP) == "LEFT"

    def test_hostname_in_header(self):
        assert gossip_status(gossipinfo("LEFT", header="node2/" + IP), IP) == "LEFT"

    def test_other_endpoint_status_is_not_used(self):
        # the endpoint listed first is NORMAL, IP itself has no STATUS
        assert gossip_status(gossipinfo(""), IP) == ""

    def test_endpoint_listed_after_is_not_used(self):
        out = gossipinfo("LEFT") + "/10.100.100.140\n  STATUS:5:NORMAL,1\n"
        assert gossip_status(out, IP) == "LEFT"

    def test_status_with_port_wins(self):
        out = gossipinfo("").replace("  RACK:11:rack1\n  TOKENS: not",
                                     "  STATUS_WITH_PORT:39:LEFT,1,2\n  STATUS:40:shutdown,true\n"
                                     "  RACK:11:rack1\n  TOKENS: not")
        assert gossip_status(out, IP) == "LEFT"


class TestMain:

    @pytest.mark.parametrize("state", ["UN", "UJ", "UL", "UM"])
    def test_live_node_is_refused(self, state):
        res, commands = run_main(status(state))
        assert isinstance(res, FailJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == (
            "{0} is {1}, a live node: assassinate only removes a dead one. "
            "Decommission it, or stop it and use removenode".format(IP, state))
        assert commands == ["status"]

    def test_live_node_is_refused_in_check_mode(self):
        res, commands = run_main(status("UN"), check_mode=True)
        assert isinstance(res, FailJson)
        assert commands == ["status"]

    @pytest.mark.parametrize("state", ["DN", "DL", "?N"])
    def test_dead_node_is_assassinated(self, state):
        res, commands = run_main(status(state))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == DONE
        assert commands == ["status", ASSASSINATE]

    def test_check_mode_does_not_run(self):
        res, commands = run_main(status("DN"), check_mode=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == DONE + " (check mode)"
        assert commands == ["status"]

    def test_unknown_endpoint_is_unchanged(self):
        res, commands = run_main(status("UN", ip="10.100.100.140"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == ABSENT
        assert commands == ["status", "gossipinfo"]

    @pytest.mark.parametrize("gossip_state", ["LEFT", "removed"])
    def test_gone_from_gossip_is_unchanged(self, gossip_state):
        res, commands = run_main(status("UN", ip="10.100.100.140"), gossipinfo(gossip_state))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == ABSENT
        assert commands == ["status", "gossipinfo"]

    @pytest.mark.parametrize("gossip_state", ["NORMAL", "shutdown", ""])
    def test_gossip_only_endpoint_is_assassinated(self, gossip_state):
        res, commands = run_main(status("UN", ip="10.100.100.140"), gossipinfo(gossip_state))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "gossipinfo", ASSASSINATE]

    def test_gossip_only_endpoint_check_mode(self):
        res, commands = run_main(status("UN", ip="10.100.100.140"), gossipinfo("shutdown"),
                                 check_mode=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "gossipinfo"]

    @pytest.mark.parametrize("value", ["node2.example.com", "node2", "10.0.0", "",
                                       IP + ":7000", IP + ":x", "[::1]:7000", "[::1]",
                                       "fe80::1%eth0"])
    def test_hostname_fails(self, value):
        res, commands = run_main(status("DN"), ip_address=value)
        assert isinstance(res, FailJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == \
            "ip_address must be an IP address (not a hostname, no port): {0}".format(value)
        assert commands == []

    def test_ipaddress_missing_fails(self):
        with patch.object(cassandra_assassinate, 'HAS_IPADDRESS', False):
            res, commands = run_main(status("DN"))
        assert isinstance(res, FailJson)
        assert 'ipaddress' in res.args[0]['msg']
        assert commands == []

    def test_ipv6_is_accepted(self):
        res, commands = run_main(status("DN", ip="::2"), ip_address="::2")
        assert isinstance(res, ExitJson)
        assert commands == ["status", "assassinate -- ::2"]

    def test_print_port(self):
        # nodetool_flags: -pp
        res, commands = run_main(status("DN", ip=IP + ":7000"))
        assert isinstance(res, ExitJson)
        assert commands == ["status", ASSASSINATE]

    def test_print_port_live_node_is_refused(self):
        # nodetool_flags: -pp
        res, commands = run_main(status("UN", ip=IP + ":7000"))
        assert isinstance(res, FailJson)
        assert commands == ["status"]

    def test_print_port_gossip_only_endpoint(self):
        # nodetool_flags: -pp
        res, commands = run_main(status("UN", ip="10.100.100.140:7000"),
                                 gossipinfo("shutdown", header="/" + IP + ":7000"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["status", "gossipinfo", ASSASSINATE]

    def test_debug_shows_only_assassinate_output(self):
        res, commands = run_main(status("DN"), debug=True)
        assert isinstance(res, ExitJson)
        assert 'stdout' not in res.args[0]
        res, commands = run_main(status("DN"), debug=True, assassinate_out="done\n")
        assert res.args[0]['stdout'] == "done"

    @pytest.mark.parametrize("what, out, commands", [
        ("status", status("DN"), ["status"]),
        ("gossipinfo", status("UN", ip="10.100.100.140"), ["status", "gossipinfo"]),
        ("assassinate", status("DN"), ["status", ASSASSINATE]),
    ])
    def test_nodetool_failure(self, what, out, commands):
        res, ran = run_main(out, gossipinfo("shutdown"), rcs={what: 2})
        assert isinstance(res, FailJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['rc'] == 2
        assert res.args[0]['stderr'] == 'error'
        assert 'stdout' not in res.args[0]
        assert res.args[0]['msg'] == \
            "nodetool {0} did not execute successfully rc: 2".format(what)
        assert ran == commands
