import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_packages_installed(host):
    # TODO Include ansible vars from file

    if host.system_info.distribution == "debian" \
            or host.system_info.distribution == "ubuntu":
        packages = [
            "procps",
            "psmisc",
            "strace",
            "net-tools",
            "tree",
            "dstat",
            "htop"
        ]
    elif host.system_info.distribution == "redhat" \
            or host.system_info.distribution == "centos":
        packages = [
            "procps-ng",
            "psmisc",
            "strace",
            "net-tools",
            "tree",
            "dstat",
            "htop"
        ]

    for item in packages:
        p = host.package(item)
        assert p.is_installed
