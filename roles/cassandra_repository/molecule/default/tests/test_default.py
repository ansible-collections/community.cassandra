import os

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


def is_redhat(host):
    return host.file("/etc/redhat-release").exists \
        or host.system_info.distribution in ("amzn", "redhat", "centos", "rocky", "almalinux")


def is_debian(host):
    return host.system_info.distribution in ("debian", "ubuntu")


def test_redhat_cassandra_repository_file(host):
    cassandra_version = get_cassandra_version(host)
    if is_redhat(host):
        f = host.file("/etc/yum.repos.d/cassandra-{0}.repo".format(cassandra_version))
        assert f.exists
        assert f.user == 'root'
        assert f.group == 'root'
        assert f.mode == 0o644
        assert "gpgkey = file:///etc/pki/rpm-gpg/apache-cassandra.asc" in f.content_string


def test_redhat_yum_search(host):
    cassandra_version = get_cassandra_version(host)
    if is_redhat(host):
        cmd = host.run("yum search cassandra --disablerepo='*' \
                            --enablerepo='cassandra-{0}'".format(cassandra_version))

        assert cmd.rc == 0
        assert "cassandra" in cmd.stdout


def test_signing_keys_installed(host):
    path = "/etc/pki/rpm-gpg/apache-cassandra.asc" if is_redhat(host) \
        else get_cassandra_apt_keyring_path(host)
    f = host.file(path)
    assert f.exists
    assert f.mode == 0o644
    assert b"-----BEGIN PGP PUBLIC KEY BLOCK-----" in f.content  # the file has Latin-1 comments
    assert not host.file(path + ".new").exists


def test_debian_cassandra_repository_file(host):
    cassandra_version = get_cassandra_version(host)
    keyring_path = get_cassandra_apt_keyring_path(host)
    if is_debian(host):
        assert not host.file("/etc/apt/sources.list.d/cassandra-{0}.list".format(cassandra_version)).exists
        f = host.file("/etc/apt/sources.list.d/cassandra-{0}.sources".format(cassandra_version))

        assert f.exists
        assert f.user == 'root'
        assert f.group == 'root'
        assert f.mode == 0o644
        assert "URIs: https://debian.cassandra.apache.org" in f.content_string
        assert "Suites: {0}".format(cassandra_version) in f.content_string
        assert "Signed-By: {0}".format(keyring_path) in f.content_string


def test_debian_apt_search(host):
    if is_debian(host):
        cmd = host.run("apt-cache policy cassandra")

        assert cmd.rc == 0
        assert "debian.cassandra.apache.org" in cmd.stdout
