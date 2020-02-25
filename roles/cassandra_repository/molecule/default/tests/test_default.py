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


def test_redhat_cassandra_repository_file(host):
    # with capsys.disabled(): #Disable autocapture of output and send to stdout N.B capsys must be passed into function
    # print(include_vars(host)['ansible_facts'])
    cassandra_version = get_cassandra_version(host)
    if host.system_info.distribution == "redhat" \
            or host.system_info.distribution == "centos":
        f = host.file("/etc/yum.repos.d/cassandra-{0}.repo".format(cassandra_version))
        assert f.exists
        assert f.user == 'root'
        assert f.group == 'root'
        assert f.mode == 0o644
        assert f.md5sum == "b1ed52b157689514ee8f895f5e2d4053"


def test_redhat_yum_search(host):
    cassandra_version = get_cassandra_version(host)
    if host.system_info.distribution == "redhat" \
            or host.system_info.distribution == "centos":
        cmd = host.run("yum search cassandra --disablerepo='*' \
                            --enablerepo='cassandra-{0}'".format(cassandra_version))

        assert cmd.rc == 0
        assert "cassandra" in cmd.stdout


def test_debian_cassandra_repository_file(host):
    cassandra_version = get_cassandra_version(host)
    if host.system_info.distribution == "debian" \
            or host.system_info.distribution == "ubuntu":
        f = host.file("/etc/apt/sources.list.d/cassandra-{0}.list".format(cassandra_version))

        assert f.exists
        assert f.user == 'root'
        assert f.group == 'root'
        assert f.mode == 0o644
        assert f.content_string.strip() == "deb http://www.apache.org/dist/cassandra/debian {0} main".format(cassandra_version)


def test_debian_apt_search(host):
    if host.system_info.distribution == "debian" \
            or host.system_info.distribution == "ubuntu":
        cmd = host.run("apt search cassandra")

        assert cmd.rc == 0
        assert "cassandra" in cmd.stdout
