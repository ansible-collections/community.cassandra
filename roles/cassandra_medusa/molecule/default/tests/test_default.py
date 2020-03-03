import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_medusa_directory(host):
    f = host.file('/etc/medusa')

    assert f.exists
    assert f.user == 'root'
    assert f.group == 'root'
    assert f.is_directory
    assert f.mode == 0o755


def test_medusa_ini_file(host):
    f = host.file('/etc/medusa/medusa.ini')

    assert f.exists
    assert f.user == 'root'
    assert f.group == 'root'
    assert f.is_file


def test_medusa_executable(host):

    if host.system_info.distribution == "redhat" \
            or host.system_info.distribution == "centos":
        cmd = host.run(". /opt/medusa/bin/activate &&\
                       export LC_ALL=en_US.utf8 &&\
                       export LANG=en_US.utf8 &&\
                       medusa --help")
    else:
        cmd = host.run(". /opt/medusa/bin/activate &&\
                       export LC_ALL=C.UTF-8 &&\
                       export LANG=C.UTF-8 &&\
                       medusa --help")

    assert cmd.rc == 0
    assert 'medusa' in cmd.stdout
    assert 'get-last-complete-cluster-backup' in cmd.stdout
