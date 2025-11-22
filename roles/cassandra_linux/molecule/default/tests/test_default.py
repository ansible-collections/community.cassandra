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


def test_time_sync_package_installed(host):
    # Legacy NTP packages (existing test expected these)
    legacy_ntp = all(host.package(p).is_installed for p in ["ntp", "ntpdate", "ntp-doc"])

    # Modern replacements
    chrony = host.package("chrony").is_installed
    timesyncd = host.package("systemd-timesyncd").is_installed

    assert legacy_ntp or chrony or timesyncd, "No supported time-sync package installed (ntp/chrony/systemd-timesyncd)"


def test_time_sync_service(host):
    # Accept any common service name provided by the supported packages:
    candidates = ["ntpd", "ntp", "chronyd", "chrony", "systemd-timesyncd"]

    def svc_up(svc_name):
        s = host.service(svc_name)
        # service() may return an object for non-existent units with False flags;
        # we require both running and enabled to consider it healthy.
        return getattr(s, "is_running", False) and getattr(s, "is_enabled", False)

    assert any(svc_up(s) for s in candidates), "No supported time-sync service is running+enabled"


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
