import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_ensure_firewalld_commands(host):
    firewalld_commands = [
        "firewall-cmd",
        "firewalld",
        "firewall-offline-cmd"
    ]
    for cmd in firewalld_commands:
        cmd = host.run("which {0}".format(cmd))

        assert cmd.rc == 0


def test_ensure_cassandra_ports_open(host):
    expected_ports = [
        '22/tcp',
        '7000/tcp',
        '7001/tcp',
        '7199/tcp',
        '9042/tcp',
        '9160/tcp'
    ]

    with host.sudo():
        # Detect firewall
        if host.exists("firewall-cmd"):
            cmd = host.run("firewall-cmd --list-ports")
            raw_ports = cmd.stdout.strip().split()
            
            # firewalld outputs exactly "7000/tcp"
            opened_ports = sorted(raw_ports)

        elif host.exists("ufw"):
            cmd = host.run("ufw status")
            opened_ports = []

            for line in cmd.stdout.splitlines():
                # Match lines like: "9042/tcp                  ALLOW       Anywhere"
                parts = line.split()
                if len(parts) > 0 and "/" in parts[0]:
                    opened_ports.append(parts[0].strip())

            opened_ports = sorted(opened_ports)

        else:
            raise AssertionError("No supported firewall found (firewalld or ufw).")

        assert opened_ports == expected_ports

