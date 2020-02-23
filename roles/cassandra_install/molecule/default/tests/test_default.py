import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_cassandra_available(host):
    cmd = host.run("cassandra -h")
    assert cmd.rc == 0


def test_nodetool_available(host):
    cmd = host.run("nodetool help")
    assert cmd.rc == 0


def test_cqlsh_available(host):
    cmd = host.run("cqlsh --version")
    assert cmd.rc == 0
    assert "cqlsh" in cmd.stdout
