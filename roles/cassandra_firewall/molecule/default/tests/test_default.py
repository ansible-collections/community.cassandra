import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')

EXPECTED_PORTS = ['22/tcp', '7000/tcp', '7001/tcp', '7199/tcp', '9042/tcp']


def is_debian(host):
    return host.system_info.distribution in ("ubuntu", "debian")


def test_ensure_firewall_commands(host):
    cmds = ["ufw"] if is_debian(host) else ["firewall-cmd", "firewalld", "firewall-offline-cmd"]
    for cmd in cmds:
        assert host.exists(cmd)


def test_ensure_cassandra_ports_open(host):
    if is_debian(host):
        lines = host.run("ufw show added").stdout.splitlines()
        opened = sorted(line.split()[-1] for line in lines if line.startswith("ufw allow "))
    else:
        # Output is not always in the same order so we need to order it ourselves
        opened = sorted(host.run("firewall-cmd --list-ports").stdout.split())

    assert opened == EXPECTED_PORTS
