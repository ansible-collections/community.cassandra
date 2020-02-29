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


def test_swap_off(host):

    f = host.file("./is_docker.txt")

    if f.exists is False:
        cmd = host.run("free | grep Swap | tr -s ' ' | cut -d ' ' -f 2")

        assert cmd.rc == 0
        assert cmd.stdout.strip() == "0"


def test_swapiness_1(host):
    cmd = host.run("cat /proc/sys/vm/swappiness")

    assert cmd.rc == 0
    assert cmd.stdout.strip() == "1"


def test_max_map_count_1048575(host):
    cmd = host.run("cat /proc/sys/vm/max_map_count")

    assert cmd.rc == 0
    assert cmd.stdout.strip() == "1048575"


def test_ntp_is_installed(host):

    nginx = host.package("ntp")
    assert nginx.is_installed

    nginx = host.package("ntpdate")
    assert nginx.is_installed

    nginx = host.package("ntp-doc")
    assert nginx.is_installed


def test_ntp_service(host):
    ntp_service = "ntpd"
    if host.system_info.distribution == "debian" \
            or host.system_info.distribution == "ubuntu":
        ntp_service = "ntp"

    s = host.service(ntp_service)
    assert s.is_running
    assert s.is_enabled


def test_limit_file(host):

    f = host.file("/etc/security/limits.conf")

    assert f.exists
    assert "cassandra" in f.content_string

    # Extra check for RH based system
    if host.system_info.distribution == "redhat" \
            or host.system_info.distribution == "centos":
        f = host.file("/etc/security/limits.d/90-nproc.conf")

        assert f.exists
        assert "nproc" in f.content_string


def test_thp_service_worked(host):

    cmd = host.run("cat /sys/kernel/mm/transparent_hugepage/enabled")

    assert cmd.rc == 0
    assert cmd.stdout.strip() == "always madvise [never]"
