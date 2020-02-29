import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_cassandra_yaml_file(host):
    f = host.file('/etc/cassandra/conf/cassandra.yaml')

    assert f.exists
    assert f.user == 'cassandra'
    assert f.group == 'cassandra'
    assert f.mode == 0o751


def test_cassandra_yaml_valid(host):
    '''
    Tests that the cassandra.yaml file is valid yaml
    '''

    cmd = host.run("python -c 'import yaml, sys; print(yaml.safe_load(sys.stdin))' < /etc/cassandra/conf/cassandra.yaml")

    assert cmd.rc == 0
