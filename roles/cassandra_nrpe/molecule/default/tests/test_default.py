import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_hosts_file(host):
    f = host.file('/etc/hosts')

    assert f.exists
    assert f.user == 'root'
    assert f.group == 'root'


def test_nrpe_path(host):
    cmd = host.run("nrpe --version")
    if cmd.rc == 3:  # old version don't support version flag
        assert "Nagios Remote Plugin Executor" in cmd.stdout
    else:
        assert cmd.rc == 0
        assert "Nagios Remote Plugin Executor" in cmd.stdout


def test_nrpe_check_disk(host):
    os = host.system_info.distribution

    if os in ["debian", "ubuntu"]:
        cmd = host.run("/usr/lib/nagios/plugins/check_disk -w 0 -c 0")
    else:
        cmd = host.run("/usr/lib64/nagios/plugins/check_disk -w 0 -c 0")

    assert cmd.rc == 0
    assert "DISK OK" in cmd.stdout


def test_nrpe_check_load(host):
    os = host.system_info.distribution

    if os in ["debian", "ubuntu"]:
        cmd = host.run("/usr/lib/nagios/plugins/check_load -w 9,9,9 -c 15,15,15")
    else:
        cmd = host.run("/usr/lib64/nagios/plugins/check_load -w 9,9,9 -c 15,15,15")

    assert cmd.rc == 0
    assert "OK - load average" in cmd.stdout


def test_nrpe_check_cassandra_cluster(host):
    cmd = host.run("/usr/local/nagios/libexec/check_cassandra_cluster")

    assert cmd.rc == 2
    # assert "quorum" in cmd.stdout


def test_npre_py_check_jmx(host):
    cmd = host.run("/usr/local/nagios/libexec/py_check_jmx")

    assert cmd.rc == 2
    assert "CRITICAL: ConnectionError HTTPConnectionPool" in cmd.stdout
