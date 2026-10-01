import os

import pytest
import testinfra.utils.ansible_runner
import yaml

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')

FILES_DIR = os.path.join(os.path.dirname(__file__), '..', 'files')
STOCK_DIR = os.path.join(FILES_DIR, 'stock-5.0.9')
COMMON_FILES = ["cassandra.yaml", "cassandra-env.sh", "jvm-server.options", "cassandra-rackdc.properties", "logback.xml"]
FILES = COMMON_FILES + ["jvm11-server.options", "jvm17-server.options"]
FILES_4X = COMMON_FILES + ["jvm8-server.options", "jvm11-server.options"]
SERIES_4X = [("40x", "4.0.21"), ("41x", "4.1.12")]
OVERRIDE_DIR = "/tmp/cassandra-override"

HEADER = "Managed by Ansible (community.cassandra.cassandra_config): change the role variables, not this file."


def header(name):
    return "<!-- %s -->" % HEADER if name.endswith(".xml") else "# " + HEADER


# Deliberate differences from stock, as the deb/rpm packages ship them.
PACKAGED = {
    "cassandra.yaml": {
        "# hints_directory: /var/lib/cassandra/hints": "hints_directory: /var/lib/cassandra/hints",
        "# data_file_directories:": "data_file_directories:",
        "#     - /var/lib/cassandra/data": "    - /var/lib/cassandra/data",
        "# commitlog_directory: /var/lib/cassandra/commitlog": "commitlog_directory: /var/lib/cassandra/commitlog",
        "# saved_caches_directory: /var/lib/cassandra/saved_caches": "saved_caches_directory: /var/lib/cassandra/saved_caches",
        # the role's own: a new 5.0 cluster starts with the 5.0 formats (not in 4.x files)
        "storage_compatibility_mode: CASSANDRA_4": "storage_compatibility_mode: NONE",
    },
    "cassandra-env.sh": {
        '    CASSANDRA_LOG_DIR="$CASSANDRA_HOME/logs"': "    CASSANDRA_LOG_DIR=/var/log/cassandra",
    },
    # and one of the role's own: no stdout copy of system.log (cassandra_log_console)
    "logback.xml": {
        '    <appender-ref ref="STDOUT" />': '    <!-- <appender-ref ref="STDOUT" /> -->',
    },
}


def conf_dir(host):
    return "/etc/cassandra/conf" if host.system_info.distribution not in ("ubuntu", "debian") else "/etc/cassandra"


def lines(host, path):
    return host.file(path).content_string.split("\n")


@pytest.mark.parametrize("name", FILES)
def test_defaults_match_stock(host, name):
    with open(os.path.join(STOCK_DIR, name + ".stock")) as f:
        expected = f.read().split("\n")
    changes = PACKAGED.get(name, {})
    expected = [header(name)] + [changes.get(line, line) for line in expected]

    assert lines(host, f"{conf_dir(host)}/{name}") == expected


JVM_4X = ["jvm8-server.options", "jvm11-server.options"]


def stock_lines(version, name):
    with open(os.path.join(FILES_DIR, f"stock-{version}", name + ".stock")) as f:
        return [header(name)] + [PACKAGED.get(name, {}).get(line, line) for line in f.read().split("\n")]


@pytest.mark.parametrize("series,version", SERIES_4X)
@pytest.mark.parametrize("name", FILES_4X)
def test_4x_defaults_match_stock(host, series, version, name):
    assert lines(host, f"/tmp/cassandra-{series}/{name}") == stock_lines(version, name)


def gc_flags(host, path):
    return [line for line in lines(host, path) if line.startswith(("-XX:+UseG1GC", "-XX:+UseConcMarkSweepGC", "-XX:+UseParNewGC"))]


@pytest.mark.parametrize("series", ["40x", "41x"])
@pytest.mark.parametrize("name", JVM_4X)
def test_4x_g1_switch(host, series, name):
    jvm = lines(host, f"/tmp/cassandra-{series}-G1/{name}")

    assert gc_flags(host, f"/tmp/cassandra-{series}-G1/{name}") == ["-XX:+UseG1GC"]
    assert "-XX:MaxGCPauseMillis=300" in jvm
    assert "-XX:InitiatingHeapOccupancyPercent=70" in jvm


def test_50x_cms_on_java11_only(host):
    assert gc_flags(host, "/tmp/cassandra-50x-CMS/jvm11-server.options") == ["-XX:+UseConcMarkSweepGC"]
    assert gc_flags(host, "/tmp/cassandra-50x-CMS/jvm17-server.options") == []


def test_4x_has_no_jvm17_file(host):
    assert not host.file("/tmp/cassandra-41x/jvm17-server.options").exists


def test_40x_overrides(host):
    conf = yaml.safe_load(host.file("/tmp/cassandra-40x-override/cassandra.yaml").content_string)
    env = lines(host, "/tmp/cassandra-40x-override/cassandra-env.sh")

    assert conf["key_cache_save_period"] == 3600  # version-dependent default is overridable
    assert conf["read_request_timeout_in_ms"] == 7000
    assert 'MAX_HEAP_SIZE="512M"' in env
    assert 'HEAP_NEWSIZE="128M"' in env
    assert lines(host, "/tmp/cassandra-40x-override/jvm8-server.options")[-2:] == ["-Dmolecule.jvm8=1", ""]
    assert conf["auto_bootstrap"] is False


@pytest.mark.parametrize("series, period, window, value", [
    ("40x", "commitlog_sync_period_in_ms", "commitlog_sync_group_window_in_ms", 15),
    ("41x", "commitlog_sync_period", "commitlog_sync_group_window", "15ms"),
    ("50x", "commitlog_sync_period", "commitlog_sync_group_window", "15ms"),
])
def test_commitlog_group_mode(host, series, period, window, value):
    # Cassandra refuses to start in group mode with a sync period: only the window is set
    content = host.file(f"/tmp/cassandra-{series}-group/cassandra.yaml").content_string
    conf = yaml.safe_load(content)

    assert conf["commitlog_sync"] == "group"
    assert conf[window] == value
    assert period not in conf
    assert f"\n# {period}: " in content


def test_commitlog_group_mode_without_window_refused(host):
    assert not host.file("/tmp/cassandra-group-no-window").exists


@pytest.mark.parametrize("name", FILES)
def test_defaults_file_mode(host, name):
    f = host.file(f"{conf_dir(host)}/{name}")

    assert f.mode == 0o640
    assert f.user == "root"
    assert f.group == "cassandra"


def test_overrides_cassandra_yaml(host):
    conf = yaml.safe_load(host.file(f"{OVERRIDE_DIR}/cassandra.yaml").content_string)

    assert conf["cluster_name"] == "Molecule Cluster"
    assert conf["num_tokens"] == 4
    assert conf["endpoint_snitch"] == "GossipingPropertyFileSnitch"
    assert conf["data_file_directories"] == ["/data/cassandra/data"]
    assert conf["seed_provider"][0]["parameters"][0]["seeds"] == "10.0.0.1:7000,10.0.0.2:7000"
    assert conf["commitlog_total_space"] == "8192MiB"
    assert conf["auto_bootstrap"] is False


def test_extra_setting_with_a_variable_refused(host):
    assert not host.file("/tmp/cassandra-extra-taken").exists


def test_overrides_tls(host):
    conf = yaml.safe_load(host.file(f"{OVERRIDE_DIR}/cassandra.yaml").content_string)
    server, client = conf["server_encryption_options"], conf["client_encryption_options"]

    assert server["internode_encryption"] == "all"
    assert server["keystore_password"] == "s3cret"
    assert server["truststore_password"] == "tru5t"
    assert server["require_client_auth"] is True
    assert server["outbound_keystore"] == "/etc/cassandra/outbound.keystore"
    assert server["outbound_keystore_password"] == "0utb0und"
    assert client["enabled"] is True
    assert client["optional"] is False
    assert client["truststore"] == "/etc/cassandra/client.truststore"
    assert "keystore_password" not in client  # left commented: unset


def test_overrides_cassandra_env(host):
    env = lines(host, f"{OVERRIDE_DIR}/cassandra-env.sh")

    assert 'MAX_HEAP_SIZE="512M"' in env
    assert "    LOCAL_JMX=no" in env


def test_overrides_jvm_options(host):
    server = lines(host, f"{OVERRIDE_DIR}/jvm-server.options")
    jvm11 = lines(host, f"{OVERRIDE_DIR}/jvm11-server.options")
    jvm17 = lines(host, f"{OVERRIDE_DIR}/jvm17-server.options")

    assert server[-3:] == ["-Dmolecule.a=1", "-Dmolecule.b=2", ""]
    assert "-XX:MaxGCPauseMillis=500" in jvm11  # common value
    assert "-XX:MaxGCPauseMillis=200" in jvm17  # per-file override wins
    assert "-XX:ParallelGCThreads=8" in jvm11
    assert "-XX:ParallelGCThreads=8" in jvm17
    assert "#-XX:ConcGCThreads=16" in jvm17  # unset stays commented as stock


def test_overrides_rackdc(host):
    rackdc = lines(host, f"{OVERRIDE_DIR}/cassandra-rackdc.properties")

    assert "dc=DC_A" in rackdc
    assert "rack=RACK_1" in rackdc
    assert "prefer_local=true" in rackdc


def test_overrides_logback(host):
    logback = host.file(f"{OVERRIDE_DIR}/logback.xml").content_string

    assert '<root level="WARN">' in logback
    assert '<!-- <appender-ref ref="ASYNCDEBUGLOG" /> -->' in logback


def test_rpm_conf_alternative(host):
    if host.system_info.distribution in ("ubuntu", "debian"):
        pytest.skip("RPM layout only")
    display = host.run("alternatives --display cassandra").stdout

    assert "link currently points to /etc/cassandra/ansible.conf" in display
    assert host.file("/etc/cassandra/conf").linked_to == "/etc/cassandra/ansible.conf"
    assert host.file("/etc/cassandra/ansible.conf/cqlshrc.sample").content_string == "package file\n"  # seeded
    # from the dir in use before (prepare on Rocky), not default.conf: its keystore came along, still Cassandra's only
    keystore = host.file("/etc/cassandra/ansible.conf/.keystore")
    if host.file("/etc/cassandra/prod.conf").exists:
        assert (keystore.content_string, keystore.user, keystore.group, keystore.mode) == ("keystore\n", "cassandra", "cassandra", 0o400)
        assert not host.file("/etc/cassandra/prod.conf/cassandra.yaml").exists  # the dir it came from, untouched
    else:
        assert not keystore.exists
    assert not host.file("/etc/cassandra/ansible.conf.seed").exists  # the temp copy, moved in place
    assert host.file("/etc/cassandra/ansible.conf/cassandra.yaml").exists
    assert not host.file("/etc/cassandra/default.conf/cassandra.yaml").exists  # package dir untouched


def test_unconfirmed_change_not_applied(host):
    conf = yaml.safe_load(host.file("/tmp/cassandra-confirm/cassandra.yaml").content_string)

    assert conf["num_tokens"] == 16
    assert "commitlog_total_space" not in conf  # the unconfirmed change was refused
    assert conf["data_file_directories"] == ["/tmp/initialized-node"]  # also when the inventory moved the data dir
    assert not host.file("/tmp/not-initialized").exists


def test_masked_password_applied(host):
    conf = yaml.safe_load(host.file("/tmp/cassandra-secret/cassandra.yaml").content_string)

    assert conf["server_encryption_options"]["keystore_password"] == "Molecule-K3ystore-Secret"


def test_identity_change_only_when_forced(host):
    conf = yaml.safe_load(host.file("/tmp/cassandra-identity/cassandra.yaml").content_string)
    rackdc = lines(host, "/tmp/cassandra-identity/cassandra-rackdc.properties")

    assert conf["num_tokens"] == 16  # refused
    assert "rack=rack2" in rackdc  # forced


def test_preview_leaves_no_temp_dir(host):
    assert host.run("ls -d /tmp/*.cassandra_config").rc != 0


def test_jmx_users(host):
    password = host.file("/etc/cassandra/jmxremote.password")
    access = host.file("/etc/cassandra/jmxremote.access")
    env = host.file("/tmp/cassandra-access/cassandra-env.sh").content_string

    assert (password.mode, password.user, password.group) == (0o400, "dbsvc", "dbgrp")  # cassandra_user/group
    assert host.run("cat /etc/cassandra/jmxremote.password").stdout.split("\n")[:2] == [
        "monitor Mon1tor-Secret", "admin Adm1n-Secret"]
    assert (access.mode, access.user, access.group) == (0o400, "dbsvc", "dbgrp")
    assert "monitor readonly" in host.run("cat /etc/cassandra/jmxremote.access").stdout
    assert "admin readwrite \\" in host.run("cat /etc/cassandra/jmxremote.access").stdout
    assert '\nJVM_OPTS="$JVM_OPTS -Dcom.sun.management.jmxremote.access.file=/etc/cassandra/jmxremote.access"' in env
    assert "LOCAL_JMX=no" in env


def test_replaced_file_backed_up(host):
    # the password change replaced cassandra.yaml of an existing config
    assert host.run("ls /tmp/cassandra-secret/cassandra.yaml.*~").rc == 0


def test_missing_data_dir_created(host):
    # "Render with overrides" sets /data/cassandra/data, which no package creates:
    # a new node could not start without it
    data = host.file("/data/cassandra/data")
    assert data.is_directory and data.user == "cassandra" and data.group == "cassandra" and data.mode == 0o750
    # its missing parents: root's, open to other tools (a log dir under /var/log/apps...)
    for parent in ("/data", "/data/cassandra"):
        d = host.file(parent)
        assert d.is_directory and d.user == "root" and d.mode == 0o755


@pytest.mark.parametrize("name", FILES)
def test_service_account_config_files(host, name):
    # cassandra_group: dbgrp, the config files follow it (cassandra_config_group)
    f = host.file(f"/tmp/cassandra-access/{name}")

    assert (f.user, f.group, f.mode) == ("root", "dbgrp", 0o640)


@pytest.mark.parametrize("path", ["/data/account/data", "/data/account/log", "/data/account/commitlog"])
def test_service_account_dirs(host, path):
    d = host.file(path)

    assert d.is_directory and (d.user, d.group, d.mode) == ("dbsvc", "dbgrp", 0o750)


def test_missing_account_refused_before_writing(host):
    # nosuchuser, and dbsvc outside the cassandra group: nothing written, no
    # directory created, the JMX users of the case before kept
    assert host.run("ls -A /tmp/cassandra-no-account").stdout == ""
    assert not host.file("/data/no-account").exists
    assert "intruder" not in host.run("cat /etc/cassandra/jmxremote.password /etc/cassandra/jmxremote.access").stdout
