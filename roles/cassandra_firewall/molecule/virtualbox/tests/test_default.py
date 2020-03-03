import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_ensure_firewalld_commands(host):
    firewalld_commands = [
        "firewall-cmd",
        "firewall-offline-cmd"
    ]
    for cmd in firewalld_commands:
        cmd = host.run("which {0}".format(cmd))

        assert cmd.rc == 0


def test_ensure_cassandra_ports_open(host):
    expected_output = ['22/tcp',
                       '7000/tcp',
                       '7001/tcp',
                       '7199/tcp',
                       '9042/tcp',
                       '9160/tcp']
    with host.sudo():
        cmd = host.run("firewall-cmd --list-ports")

        # Output is not always in the same order so we need to order it ourselves
        assert sorted(cmd.stdout.strip().split(" ")) == expected_output
