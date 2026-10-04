from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from ansible_collections.community.cassandra.plugins.modules import cassandra_decommission

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

# nodetool netstats of a Cassandra 5.0 node; the Mode line is printed the
# same way ("Mode: %s") by 4.0, 4.1 and 5.0.
NETSTATS = """Mode: {mode}
Not sending any streams.
Read Repair Statistics:
Attempted: 0
Mismatch (Blocking): 0
Mismatch (Background): 0
Pool Name                    Active   Pending      Completed   Dropped
Large messages                  n/a         0              0         0
Small messages                  n/a         0              0         0
Gossip messages                 n/a         0              0         0
"""

NETSTATS_LEAVING = """Mode: LEAVING
Unbootstrap 5a8d3a10-7c5e-11ef-9b1c-5f2e8c1d4a7b
    /127.0.0.2
        Sending 12 files, 104857600 bytes total. Already sent 3 files, 26214400 bytes total
Read Repair Statistics:
Attempted: 0
Mismatch (Blocking): 0
Mismatch (Background): 0
Pool Name                    Active   Pending      Completed   Dropped
Large messages                  n/a         0              0         0
Small messages                  n/a         0              3         0
Gossip messages                 n/a         0            120         0
"""

FAILED_MSG = ("the previous decommission of this node failed: find the cause in the logs "
              "(disk space on the receiving nodes, network, timeouts), then run nodetool "
              "decommission by hand to resume it")

LEAVING_MSG = ("decommission already in progress on this node (on 4.0/4.1 a failed "
               "decommission also stays LEAVING: check the logs)")


def netstats(mode):
    return NETSTATS.format(mode=mode)


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


def run_main(netstats_out, check_mode=False, debug=False, netstats_rc=0,
             decommission_rc=0, decommission_out='', decommission_err=''):
    """Run main() with nodetool mocked; return (exception, list of nodetool sub-commands)."""
    FakeModule.params = {'host': '127.0.0.1', 'port': 7199, 'debug': debug,
                         '_check_mode': check_mode}
    commands = []

    class FakeNodeTool(object):

        def __init__(self, module, cmd):
            self.cmd = cmd

        def run_command(self):
            commands.append(self.cmd)
            if self.cmd == "netstats":
                return netstats_rc, netstats_out, 'netstats error' if netstats_rc else ''
            return decommission_rc, decommission_out, decommission_err

    with patch.object(cassandra_decommission, 'AnsibleModule', FakeModule), \
            patch.object(cassandra_decommission, 'NodeToolCommandSimple', FakeNodeTool):
        with pytest.raises((ExitJson, FailJson)) as exc:
            cassandra_decommission.main()
    return exc.value, commands


class TestMain:

    def test_normal_runs_decommission(self):
        res, commands = run_main(netstats("NORMAL"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['msg'] == "decommission command succeeded"
        assert commands == ["netstats", "decommission"]

    def test_normal_debug_returns_decommission_output(self):
        res, commands = run_main(netstats("NORMAL"), debug=True, decommission_out="done\n")
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert res.args[0]['stdout'] == "done"
        assert 'stderr' not in res.args[0]

    def test_normal_check_mode_does_not_run(self):
        res, commands = run_main(netstats("NORMAL"), check_mode=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is True
        assert commands == ["netstats"]

    def test_decommission_failure(self):
        res, commands = run_main(netstats("NORMAL"), decommission_rc=2,
                                 decommission_err="nodetool: error")
        assert isinstance(res, FailJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == "decommission command failed"
        assert res.args[0]['rc'] == 2
        assert 'stderr' not in res.args[0]
        assert commands == ["netstats", "decommission"]

    def test_decommission_failure_debug(self):
        res, commands = run_main(netstats("NORMAL"), debug=True, decommission_rc=2,
                                 decommission_err="nodetool: error")
        assert isinstance(res, FailJson)
        assert res.args[0]['stderr'] == "nodetool: error"
        assert res.args[0]['stdout'].startswith("Mode: NORMAL")

    def test_debug_returns_netstats(self):
        res, commands = run_main(netstats("DECOMMISSIONED"), debug=True)
        assert isinstance(res, ExitJson)
        assert res.args[0]['stdout'].startswith("Mode: DECOMMISSIONED")
        assert 'stderr' not in res.args[0]

    def test_decommissioned_is_unchanged(self):
        res, commands = run_main(netstats("DECOMMISSIONED"))
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == "already decommissioned"
        assert commands == ["netstats"]

    @pytest.mark.parametrize("out", [netstats("LEAVING"), NETSTATS_LEAVING])
    def test_leaving_is_unchanged(self, out):
        res, commands = run_main(out)
        assert isinstance(res, ExitJson)
        assert res.args[0]['changed'] is False
        assert res.args[0]['msg'] == LEAVING_MSG
        assert commands == ["netstats"]

    @pytest.mark.parametrize("check_mode", [False, True])
    def test_failed_decommission_is_not_retried(self, check_mode):
        res, commands = run_main(netstats("DECOMMISSION_FAILED"), check_mode=check_mode)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == FAILED_MSG
        assert commands == ["netstats"]

    @pytest.mark.parametrize("mode", ["STARTING", "JOINING", "JOINING_FAILED", "MOVING",
                                      "DRAINING", "DRAINED"])
    def test_other_mode_fails(self, mode):
        res, commands = run_main(netstats(mode))
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == "node mode is {0}, not NORMAL: not decommissioning".format(mode)
        assert commands == ["netstats"]

    def test_no_mode_line_fails(self):
        res, commands = run_main("Not sending any streams.\n")
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == \
            "no Mode line in the nodetool netstats output: not decommissioning"
        assert commands == ["netstats"]

    @pytest.mark.parametrize("debug", [False, True])
    def test_netstats_failure(self, debug):
        res, commands = run_main('', debug=debug, netstats_rc=1)
        assert isinstance(res, FailJson)
        assert res.args[0]['msg'] == "nodetool netstats failed: not decommissioning"
        assert res.args[0]['rc'] == 1
        assert ('stderr' in res.args[0]) is debug
        assert commands == ["netstats"]
