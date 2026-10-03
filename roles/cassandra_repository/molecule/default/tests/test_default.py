import os

import pytest

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def include_vars(host):
    ansible = host.ansible('include_vars',
                           'file="../../defaults/main.yml"',
                           False,
                           False)
    return ansible


def get_cassandra_version(host):
    return include_vars(host)['ansible_facts']['cassandra_version']


def get_cassandra_apt_keyring_path(host):
    return include_vars(host)['ansible_facts']['cassandra_apt_keyring_path']


@pytest.fixture(scope="module")
def os_family(host):
    return host.ansible("setup", "filter=ansible_os_family")["ansible_facts"]["ansible_os_family"]


@pytest.fixture
def redhat_only(os_family):
    if os_family != "RedHat":
        pytest.skip("RedHat family only")


@pytest.fixture
def debian_only(os_family):
    if os_family != "Debian":
        pytest.skip("Debian family only")


@pytest.mark.usefixtures("redhat_only")
def test_redhat_cassandra_repository_file(host):
    cassandra_version = get_cassandra_version(host)
    f = host.file("/etc/yum.repos.d/cassandra-{0}.repo".format(cassandra_version))
    assert f.exists
    assert f.user == 'root'
    assert f.group == 'root'
    assert f.mode == 0o644
    assert "gpgkey = file:///etc/pki/rpm-gpg/apache-cassandra.asc" in f.content_string


@pytest.mark.usefixtures("redhat_only")
def test_redhat_yum_search(host):
    cassandra_version = get_cassandra_version(host)
    cmd = host.run("yum search cassandra --disablerepo='*' \
                        --enablerepo='cassandra-{0}'".format(cassandra_version))

    assert cmd.rc == 0
    assert "cassandra" in cmd.stdout


def test_signing_keys_installed(host, os_family):
    path = "/etc/pki/rpm-gpg/apache-cassandra.asc" if os_family == "RedHat" \
        else get_cassandra_apt_keyring_path(host)
    f = host.file(path)
    assert f.exists
    assert f.mode == 0o644
    assert b"-----BEGIN PGP PUBLIC KEY BLOCK-----" in f.content  # the file has Latin-1 comments
    assert not host.file(path + ".new").exists


@pytest.mark.usefixtures("debian_only")
def test_debian_cassandra_repository_file(host):
    cassandra_version = get_cassandra_version(host)
    keyring_path = get_cassandra_apt_keyring_path(host)
    assert not host.file("/etc/apt/sources.list.d/cassandra-{0}.list".format(cassandra_version)).exists
    f = host.file("/etc/apt/sources.list.d/cassandra-{0}.sources".format(cassandra_version))

    assert f.exists
    assert f.user == 'root'
    assert f.group == 'root'
    assert f.mode == 0o644
    assert "URIs: https://debian.cassandra.apache.org" in f.content_string
    assert "Suites: {0}".format(cassandra_version) in f.content_string
    assert "Signed-By: {0}".format(keyring_path) in f.content_string


@pytest.mark.usefixtures("debian_only")
def test_debian_apt_search(host):
    cmd = host.run("apt-cache policy cassandra")

    assert cmd.rc == 0
    assert "debian.cassandra.apache.org" in cmd.stdout
