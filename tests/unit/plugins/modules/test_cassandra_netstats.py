from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pytest

from ansible_collections.community.cassandra.plugins.modules import cassandra_netstats

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

NETSTATS_NORMAL = """Mode: NORMAL
Not sending any streams.
Read Repair Statistics:
Attempted: 0
Mismatch (Blocking): 0
Mismatch (Background): 0
Pool Name                    Active   Pending      Completed   Dropped
Large messages                  n/a         0              0         0
"""

NETSTATS_LEAVING = """Mode: LEAVING
Unbootstrap 5a8d3a10-7c5e-11ef-9b1c-5f2e8c1d4a7b
    /127.0.0.2
        Sending 12 files, 104857600 bytes total. Already sent 3 files, 26214400 bytes total
Read Repair Statistics:
Attempted: 0
Pool Name                    Active   Pending      Completed   Dropped
"""


class ExitJson(Exception):
    pass


class FailJson(Exception):
    pass


class FakeModule(object):

    def __init__(self, argument_spec=None, supports_check_mode=False):
        self.params = dict(FakeModule.params)

    def exit_json(self, **kwargs):
        raise ExitJson(kwargs)

    def fail_json(self, **kwargs):
        raise FailJson(kwargs)


def run_main(out, rc=0, err='', debug=False):
    """Run main() with nodetool mocked; return the exception raised by exit_json or fail_json."""
    FakeModule.params = {'host': '127.0.0.1', 'port': 7199, 'debug': debug}
    commands = []

    class FakeNodeTool(object):

        def __init__(self, module, cmd):
            commands.append(cmd)

        def run_command(self):
            return rc, out, err

    with patch.object(cassandra_netstats, 'AnsibleModule', FakeModule), \
            patch.object(cassandra_netstats, 'NodeToolCommandSimple', FakeNodeTool):
        with pytest.raises((ExitJson, FailJson)) as exc:
            cassandra_netstats.main()
    assert commands == ['netstats']
    return exc.value


def test_normal():
    exc = run_main(NETSTATS_NORMAL)
    assert isinstance(exc, ExitJson)
    result = exc.args[0]
    assert result['mode'] == 'NORMAL'
    assert result['streams'] == []
    assert result['streaming'] is False
    assert result['stdout'] == NETSTATS_NORMAL
    assert 'changed' not in result
    assert 'stderr' not in result


def test_leaving_streaming():
    result = run_main(NETSTATS_LEAVING).args[0]
    assert result['mode'] == 'LEAVING'
    assert result['streaming'] is True
    assert result['streams'] == [
        "Unbootstrap 5a8d3a10-7c5e-11ef-9b1c-5f2e8c1d4a7b",
        "    /127.0.0.2",
        "        Sending 12 files, 104857600 bytes total. Already sent 3 files, 26214400 bytes total",
    ]


def test_no_mode_line():
    result = run_main("Not sending any streams.\n").args[0]
    assert result['mode'] == ''
    assert result['streaming'] is False


def test_nodetool_fails():
    exc = run_main('', rc=1, err='nodetool: Failed to connect', debug=True)
    assert isinstance(exc, FailJson)
    assert exc.args[0]['msg'] == "netstats command failed"
    assert exc.args[0]['stderr'] == 'nodetool: Failed to connect'


def test_nodetool_fails_no_debug():
    exc = run_main('', rc=1, err='nodetool: Failed to connect')
    assert isinstance(exc, FailJson)
    assert 'stderr' not in exc.args[0]


def test_stderr_with_debug():
    result = run_main(NETSTATS_NORMAL, err='a warning', debug=True).args[0]
    assert result['stderr'] == 'a warning'
    assert result['mode'] == 'NORMAL'
