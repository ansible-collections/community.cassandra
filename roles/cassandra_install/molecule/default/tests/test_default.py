import os

import pytest

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


@pytest.fixture(scope="module")
def os_family(host):
    return host.ansible("setup", "filter=ansible_os_family")["ansible_facts"]["ansible_os_family"]


@pytest.fixture
def debian_only(os_family):
    if os_family != "Debian":
        pytest.skip("Debian family only")


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


@pytest.mark.parametrize("tool", ["sstablemetadata", "sstabledump", "sstablesplit", "sstableofflinerelevel"])
def test_cassandra_tools_available(host, tool):
    assert host.exists(tool)


def test_jemalloc_found_by_ldconfig(host, os_family):
    # Optional on RedHat-likes: only there when a repo (EPEL, Amazon) has it
    if os_family == "RedHat" and not host.run("dnf -q repoquery jemalloc").stdout:
        pytest.skip("jemalloc not in any enabled repo")

    assert "libjemalloc.so" in host.run("ldconfig -p").stdout


def test_java_17_only(host):
    cmd = host.run("java -version")

    assert cmd.rc == 0
    assert 'version "17.' in cmd.stderr
    assert host.run("ls -d /usr/lib/jvm/*11*").rc != 0


@pytest.mark.usefixtures("debian_only")
def test_policy_rc_d_removed(host):
    # side_effect.yml left one from an interrupted run before running the role again
    assert not host.file("/usr/sbin/policy-rc.d").exists


def test_cassandra_not_started_by_package(host):
    assert host.run("pgrep -f [C]assandraDaemon").rc != 0


def test_no_cqlsh_python_override_on_50x(host):
    # 5.0's cqlsh supports the system python3: no pointers written
    assert not host.file("/etc/profile.d/cqlsh.sh").exists
    assert not host.file("/etc/sudoers.d/cqlsh").exists


def test_cqlsh_installed_by_hand_kept(host):
    # side_effect.yml put one in /usr/local/bin, without the role's marker
    assert "installed by hand" in host.file("/usr/local/bin/cqlsh").content_string


def test_dsbulk_installed_like_the_tools(host):
    assert host.run("readlink /usr/bin/dsbulk").stdout.strip() == "/usr/share/dsbulk/bin/dsbulk"
    assert host.run("readlink /usr/share/dsbulk").stdout.strip() == "/usr/share/dsbulk-1.11.2"
    # side_effect.yml went to 1.11.1 and back: 1.11.1 went, the one unpacked by hand stays
    assert host.run("ls -d /usr/share/dsbulk-*").stdout.split() == ["/usr/share/dsbulk-1.0.0", "/usr/share/dsbulk-1.11.2"]

    # root-owned, nothing writable by group or others
    assert host.run("find /usr/share/dsbulk-1.11.2 ! -user root -o ! -group root -o -perm /022").stdout == ""
    assert host.file("/usr/share/dsbulk-1.11.2/bin/dsbulk").mode == 0o755


def test_dsbulk_runs(host):
    cmd = host.run("dsbulk --version")

    assert cmd.rc == 0
    assert "v1.11.2" in cmd.stdout


def test_dsbulk_starts_its_driver(host):
    # Loads the driver and Netty on the installed Java, no Cassandra needed;
    # dsbulk writes its logs in ./logs
    cmd = host.run("cd /tmp && dsbulk count -k ks -t t -h 127.0.0.1 -port 1")

    assert "Could not reach any contact point" in cmd.stdout + cmd.stderr
