from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

# cassandra_config shows what it would change (secrets masked), asks before
# changing an initialized node and refuses to change the identity of a joined node.

import json
import os
import subprocess
import sys

import pytest
import yaml

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

try:  # ansible-core 2.19+ renders trusted templates only
    from ansible.template import trust_as_template
except ImportError:
    def trust_as_template(template):
        return template

TASKS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "roles", "cassandra_config", "tasks")
HEADER = "# Managed by Ansible (community.cassandra.cassandra_config): change the role variables, not this file.\n"


def task(name):
    with open(os.path.join(TASKS, "main.yml"), encoding="utf-8") as f:
        todo = list(yaml.safe_load(f))
    while todo:
        t = todo.pop(0)
        if t.get("name") == name:
            return t
        todo += t.get("block", []) + t.get("rescue", []) + t.get("always", [])
    raise KeyError(name)


def render(template, **variables):
    return Templar(loader=DataLoader(), variables=variables).template(trust_as_template(template))


SCRIPT = task("Diff them against the live files")["ansible.builtin.command"]["argv"][2]


def preview(tmp_path, name, live, new):
    """The preview's output for a live file (None: none yet) and the role's."""
    (tmp_path / "live").mkdir()
    (tmp_path / "new").mkdir()
    live_path, new_path = tmp_path / "live" / name, tmp_path / "new" / name
    if live is not None:
        live_path.write_bytes(live.encode())
    new_path.write_bytes(new.encode())
    return subprocess.run([sys.executable, "-c", SCRIPT, str(live_path), str(new_path)],
                          stdout=subprocess.PIPE, check=True).stdout.decode()


def changed_lines(diff):
    return [line for line in diff.split("\n") if line[:1] in ("+", "-") and line[:3] not in ("+++", "---")]


def test_same_file_no_diff(tmp_path):
    assert preview(tmp_path, "jvm-server.options", HEADER + "-Xss256k\n", HEADER + "-Xss256k\n") == ""


def test_new_file_shown_whole(tmp_path):
    assert changed_lines(preview(tmp_path, "jvm-server.options", None, HEADER + "-Xss256k\n")) == [
        "+" + HEADER.rstrip("\n"), "+-Xss256k"]


def test_crlf_is_a_change(tmp_path):
    # bash reads X=8G\r as "8G\r": the live file must show as different
    assert changed_lines(preview(tmp_path, "cassandra-env.sh", "X=8G\r\n", "X=8G\n")) == ["-X=8G\r", "+X=8G"]


@pytest.mark.parametrize("live, new, shown", [
    ("  keystore_password: old1\n", "  keystore_password: new2\n",
     ["-  keystore_password: ****", "+  keystore_password: ****"]),
    ('  truststore_password: "old1"\n', "  truststore_password: new2\n",
     ["-  truststore_password: ****", "+  truststore_password: ****"]),
    # quotes, a space or a # in the value: all of it masked
    ("  keystore_password: 'a b'\n", '  keystore_password: "c#d" # new\n',
     ["-  keystore_password: ****", "+  keystore_password: ****"]),
    ("keystore_password: x\r\n", "keystore_password: y\n", ["-keystore_password: ****\r", "+keystore_password: ****"]),
    ("tde_key_password=old1\n", "tde_key_password=new2\n", ["-tde_key_password=****", "+tde_key_password=****"]),
    ("secret: a\n", "secret: b\n", ["-secret: ****", "+secret: ****"]),
    ("num_tokens: 16\n", "num_tokens: 8\n", ["-num_tokens: 16", "+num_tokens: 8"]),
])
def test_secrets_masked_in_the_diff(tmp_path, live, new, shown):
    assert changed_lines(preview(tmp_path, "cassandra.yaml", live, new)) == shown


# an ASCII locale (LANG=C, no UTF-8 mode, as on Python 3.6) and a UTF-8 one
LOCALES = [dict(os.environ, LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0"), dict(os.environ, LC_ALL="C.UTF-8")]


@pytest.mark.parametrize("env", LOCALES)
@pytest.mark.parametrize("live", [b"# caf\xe9\nnum_tokens: 16\n", u"# caf\xe9\nnum_tokens: 16\n".encode("utf-8")])
def test_diff_reads_any_live_file(tmp_path, env, live):
    # a Latin-1 comment, or any UTF-8 text under an ASCII locale: read as UTF-8, a bad byte replaced
    (tmp_path / "live").write_bytes(live)
    (tmp_path / "new").write_bytes(u"# caf\xe9\nnum_tokens: 8\n".encode("utf-8"))
    out = subprocess.run([sys.executable, "-c", SCRIPT, str(tmp_path / "live"), str(tmp_path / "new")],
                         stdout=subprocess.PIPE, check=True, env=env).stdout.decode("utf-8")
    assert {"-num_tokens: 16", "+num_tokens: 8"} <= set(changed_lines(out))


def test_diff_of_a_path_not_in_utf8(tmp_path):
    # the live path is in the diff header: the output stays valid UTF-8 with an undecodable byte there
    d = os.path.join(str(tmp_path).encode(), b"caf\xe9")
    os.mkdir(d)
    for name, text in ((b"live", b"num_tokens: 16\n"), (b"new", b"num_tokens: 8\n")):
        with open(os.path.join(d, name), "wb") as f:
            f.write(text)
    out = subprocess.run([sys.executable.encode(), b"-c", SCRIPT.encode(), os.path.join(d, b"live"), os.path.join(d, b"new")],
                         stdout=subprocess.PIPE, check=True, env=LOCALES[0]).stdout.decode("utf-8")
    assert {"-num_tokens: 16", "+num_tokens: 8"} <= set(changed_lines(out))


VALIDATE = task("Check the new cassandra.yaml is valid YAML")["ansible.builtin.command"]["argv"][2]


@pytest.mark.parametrize("env", LOCALES)
def test_yaml_validation_of_utf8_text(tmp_path, env):
    (tmp_path / "cassandra.yaml").write_bytes(u"cluster_name: 'caf\xe9'\n".encode("utf-8"))
    subprocess.run([sys.executable, "-c", VALIDATE, str(tmp_path / "cassandra.yaml")], check=True, env=env)


@pytest.mark.parametrize("text, error", [
    ("cluster_name: 'X'\nnum_tokens: 16\n", None),
    ("cluster_name: 'X'\nkeystore_password: a: Secret-Value\n", "the new cassandra.yaml is not valid YAML (line 2)"),
])
def test_yaml_validation(tmp_path, text, error):
    (tmp_path / "cassandra.yaml").write_text(text)
    out = subprocess.run([sys.executable, "-c", VALIDATE, str(tmp_path / "cassandra.yaml")],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False)
    assert (out.returncode == 0) is (error is None)
    if error:  # its line only, never the text (it may hold a password)
        assert out.stderr.strip() == error and "Secret-Value" not in out.stdout + out.stderr


SYSTEM = task("Look for the system keyspace of an initialized node")["ansible.builtin.command"]["argv"][2]


def system_dirs(tmp_path, live, inventory_dirs, system_in, pyyaml=True):
    for d in system_in:
        (tmp_path / d / "system").mkdir(parents=True)
    if live is not None:
        (tmp_path / "cassandra.yaml").write_text(live.replace("@", str(tmp_path) + "/"))
    # -S: no site-packages, so no PyYAML: the script's own parser
    args = [str(tmp_path / "cassandra.yaml"), json.dumps([str(tmp_path / d) for d in inventory_dirs]), str(tmp_path / "default")]
    argv = [sys.executable] + ([] if pyyaml else ["-S"]) + ["-c", SYSTEM] + args
    out = subprocess.run(argv, stdout=subprocess.PIPE, universal_newlines=True, check=True).stdout
    # the dirs found (a "(key in the live cassandra.yaml)" line: see test_initialized_when_live_dirs_not_read)
    return [line[len(str(tmp_path)) + 1:] for line in out.split("\n") if line.startswith(str(tmp_path))]


@pytest.mark.parametrize("live, inventory_dirs, system_in, found", [
    (None, ["d1", "d2"], [], []),
    (None, ["d1", "d2"], ["d2"], ["d2"]),  # JBOD reordered in the inventory
    # the inventory does not match the node yet: its live cassandra.yaml does
    ("data_file_directories:\n    - @old1  # disk 1\n    - '@old2'\ncommitlog_directory: x\n", ["d1"], ["old2"], ["old2"]),
    ("data_file_directories: # JBOD\n    - @old1\n", ["d1"], ["old1"], ["old1"]),
    ("local_system_data_file_directory: \"@sys\"\n", ["d1"], ["sys"], ["sys"]),
    ("# local_system_data_file_directory: @sys\n", ["d1"], ["sys"], []),
    # other layouts YAML reads the same: items at column 0, a flow list, blank and comment lines between items
    ("data_file_directories:\n- @old1\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories: [@old0, '@old1']\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories:\n    - @old0\n\n#    - @old9\n    - @old1\nnum_tokens: 16\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories: [\n  @old0,\n  @old1 ]\nnum_tokens: 16\n", ["d1"], ["old1"], ["old1"]),
    ('"data_file_directories" :\n  - &a @old1\n', ["d1"], ["old1"], ["old1"]),
    ("\ufeffdata_file_directories:\n  -\n    @old1\n", ["d1"], ["old1"], ["old1"]),
    ("cluster_name: 'caf\xe9'\ndata_file_directories:\n  - @old1\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories:\n  - @h#1\n", ["d1"], ["h#1"], ["h#1"]),  # a comment starts after a space only
    ("data_file_directories: [@old0]\nnum_tokens: 16\ndata_file_directories: [@old0,\n@old1]\n", ["d1"], ["old0", "old1"],
     ["old0", "old1"]),  # set twice: the last one
    # none set: Cassandra's default data dir
    ("cluster_name: x\n# data_file_directories:\n#     - @old1\n", ["d1"], ["default"], ["default"]),
    ("data_file_directories:\nnum_tokens: 16\n", ["d1"], ["default"], ["default"]),
    ("data_file_directories:\n  - @old1\n", ["d1"], ["default"], []),  # set: not the default
])
@pytest.mark.parametrize("pyyaml", [True, False])
def test_initialized_node_found(tmp_path, live, inventory_dirs, system_in, found, pyyaml):
    assert system_dirs(tmp_path, live, inventory_dirs, system_in, pyyaml) == found


@pytest.mark.parametrize("live, key", [
    ("data_file_directories:\n  - !!str data\n", "data_file_directories"),
    ("data_file_directories:\n  - @sp ace\n", "data_file_directories"),  # cut at the space: not a dir
    ("local_system_data_file_directory: '@x y'\n", "local_system_data_file_directory"),
])
def test_initialized_when_live_dirs_not_read(tmp_path, live, key):
    # without PyYAML, a value it cannot read for sure counts as initialized: one prompt too many at worst
    (tmp_path / "cassandra.yaml").write_text(live.replace("@", str(tmp_path) + "/"))
    out = subprocess.run([sys.executable, "-S", "-c", SYSTEM, str(tmp_path / "cassandra.yaml"), "[]", "/nonexistent"],
                         stdout=subprocess.PIPE, universal_newlines=True, check=True).stdout
    assert out.split("\n")[0] == "(%s in the live cassandra.yaml)" % key


@pytest.mark.parametrize("live, key", [
    ("data_file_directories:\n  - data\n", "data_file_directories"),  # relative: to a cwd not known here
    ("data_file_directories:\n  - @d\n  - data\n", "data_file_directories"),
    ("data_file_directories: @d\n", "data_file_directories"),  # a single value, not a list
    ("data_file_directories: '/'\n", "data_file_directories"),
    ("local_system_data_file_directory: sys\n", "local_system_data_file_directory"),
])
@pytest.mark.parametrize("pyyaml", [True, False])
def test_initialized_when_live_dirs_relative_or_single(tmp_path, live, key, pyyaml):
    (tmp_path / "d").mkdir()  # exists, without a system keyspace
    (tmp_path / "cassandra.yaml").write_text(live.replace("@", str(tmp_path) + "/"))
    argv = [sys.executable] + ([] if pyyaml else ["-S"]) + ["-c", SYSTEM, str(tmp_path / "cassandra.yaml"), "[]", "/nonexistent"]
    out = subprocess.run(argv, stdout=subprocess.PIPE, universal_newlines=True, check=True, cwd=str(tmp_path)).stdout
    assert "(%s in the live cassandra.yaml)" % key in out.split("\n")


def test_new_node_not_initialized_without_pyyaml(tmp_path):
    # the packaged cassandra.yaml of a new node: existing data dir, no system keyspace, comments
    (tmp_path / "data").mkdir()
    (tmp_path / "cassandra.yaml").write_text("data_file_directories:  # JBOD\n    - %s/data\n# local_system_data_file_directory: /x\n"
                                             "commitlog_directory: /c\n" % tmp_path)
    out = subprocess.run([sys.executable, "-S", "-c", SYSTEM, str(tmp_path / "cassandra.yaml"), "[]", "/nonexistent"],
                         stdout=subprocess.PIPE, universal_newlines=True, check=True).stdout
    assert out.strip() == ""


def test_live_file_not_utf8(tmp_path):
    (tmp_path / "cassandra.yaml").write_bytes(b"# caf\xe9\ndata_file_directories:\n  - " + str(tmp_path).encode() + b"/d\n")
    (tmp_path / "d" / "system").mkdir(parents=True)
    for argv in ([sys.executable], [sys.executable, "-S"]):
        out = subprocess.run(argv + ["-c", SYSTEM, str(tmp_path / "cassandra.yaml"), "[]", "/nonexistent"], stdout=subprocess.PIPE,
                             universal_newlines=True, check=True, env=dict(os.environ, LC_ALL="C", PYTHONUTF8="0")).stdout
        assert out.split() == [str(tmp_path / "d")]


@pytest.mark.parametrize("system, name, service, initialized", [
    (["/data/system"], "cassandra.service", "stopped", True), ([], "cassandra.service", "running", True),
    ([], "cassandra", "running", True),  # a sysv init script, no systemd
    ([], "cassandra.service", "stopped", False), ([], None, None, False),
])
def test_initialized_when_system_found_or_running(system, name, service, initialized):
    template = task("Tell whether this node was already initialized")["ansible.builtin.set_fact"]["_cassandra_config_initialized"]
    services = {name: {"state": service}} if name else {}
    assert render(template, cassandra_config_system={"stdout_lines": system}, ansible_facts={"services": services}) is initialized


IDENTITY = task("Compare the settings a joined node must keep")["ansible.builtin.command"]["argv"][2]


@pytest.mark.parametrize("live, new, changes", [
    ("cluster_name: \"it's\"\nnum_tokens: 16\n", "cluster_name: 'it''s'\nnum_tokens: 16\n", []),
    ("cluster_name: 'X' # prod\nnum_tokens: 16 # fixed\n", "cluster_name: 'X'\nnum_tokens: 16\n", []),
    ("cluster_name: 'X'\ninitial_token: 0\n", "cluster_name: 'X'\nnum_tokens: 1\ninitial_token: 0\n", []),
    ("cluster_name: \"say \\\"hi\\\" a\\\\b\"\n", "cluster_name: 'say \"hi\" a\\b'\n", []),
    ("cluster_name: 'X'\nnum_tokens: 16\n", "cluster_name: 'Y'\nnum_tokens: 256\n",
     ["cluster_name: X -> Y", "num_tokens: 16 -> 256"]),
])
def test_identity_compared_as_yaml_reads_it(tmp_path, live, new, changes):
    assert identity_changes(tmp_path, live, new) == changes


def identity_changes(tmp_path, live, new, live_rackdc="dc=d\n", new_rackdc="dc=d\n"):
    for name, text in (("live.yaml", live), ("new.yaml", new), ("live.p", live_rackdc), ("new.p", new_rackdc)):
        (tmp_path / name).write_text(text)
    out = subprocess.run([sys.executable, "-c", IDENTITY] + [str(tmp_path / n) for n in ("live.yaml", "new.yaml", "live.p", "new.p")],
                         stdout=subprocess.PIPE, universal_newlines=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.parametrize("env", LOCALES)
def test_identity_reads_any_live_file(tmp_path, env):
    for name, text in (("live.yaml", b"# caf\xe9\ncluster_name: 'X'\n"), ("new.yaml", u"# caf\xe9\ncluster_name: 'Y'\n".encode("utf-8")),
                       ("live.p", u"dc=d\xe9\n".encode("utf-8")), ("new.p", b"dc=d\xe9\n")):
        (tmp_path / name).write_bytes(text)
    out = subprocess.run([sys.executable, "-c", IDENTITY] + [str(tmp_path / n) for n in ("live.yaml", "new.yaml", "live.p", "new.p")],
                         stdout=subprocess.PIPE, check=True, env=env)
    assert json.loads(out.stdout.decode()) == [u"cluster_name: X -> Y", u"dc: d\xe9 -> d\ufffd"]


def test_rack_comment_is_part_of_the_value(tmp_path):
    # properties have no inline comment: the snitch's rack is "r1 # old"
    assert identity_changes(tmp_path, "num_tokens: 16\n", "num_tokens: 16\n", "rack=r1 # old\n", "rack=r1\n") == [
        "rack: r1 # old -> r1"]


@pytest.mark.parametrize("live_rackdc, new_rackdc, changes", [
    ('dc="d"\n', "dc=d\n", ['dc: "d" -> d']),  # properties keep quotes: "d" is another dc
    ("dc=d\ndc_suffix=_prod\n", "dc=d\n#dc_suffix=\n", ["dc_suffix: _prod -> "]),
    ("dc=d\nec2_naming_scheme=legacy\n", "dc=d\n# ec2_naming_scheme=standard\n",
     ["ec2_naming_scheme: legacy -> standard"]),
    ("dc=d\nec2_naming_scheme=standard\ndc_suffix=\n", "dc=d\n", []),  # the defaults, written out
])
def test_cloud_snitch_names_kept(tmp_path, live_rackdc, new_rackdc, changes):
    assert identity_changes(tmp_path, "num_tokens: 16\n", "num_tokens: 16\n", live_rackdc, new_rackdc) == changes


@pytest.mark.parametrize("live, changes", [
    # a comment after the value, other quotes: the same identity
    ("cluster_name: Prod Cluster   # prod\nnum_tokens: 16  # vnodes\n", []),
    ('cluster_name: "Prod Cluster"\nnum_tokens: 16\n', []),
    ("cluster_name: 'Prod Cluster'\nnum_tokens: 8\nnum_tokens: 16\n", []),  # set twice: the last one
    ("cluster_name: Other\nnum_tokens: 16\n", ["cluster_name: Other -> Prod Cluster"]),
])
def test_identity_of_a_joined_node_as_cassandra_reads_it(tmp_path, live, changes):
    (tmp_path / "live.yaml").write_text(live)
    (tmp_path / "new.yaml").write_text("cluster_name: 'Prod Cluster'\nnum_tokens: 16\n")
    for name in ("live.properties", "new.properties"):
        (tmp_path / name).write_text("dc=dc1\nrack=r1\n")
    out = subprocess.run([sys.executable, "-c", IDENTITY] + [str(tmp_path / n) for n in (
        "live.yaml", "new.yaml", "live.properties", "new.properties")], stdout=subprocess.PIPE, check=True).stdout
    assert json.loads(out) == changes


@pytest.mark.parametrize("live, new, changes", [
    # one step forward at a time, from what the live file says
    ("storage_compatibility_mode: CASSANDRA_4\n", "storage_compatibility_mode: UPGRADING\n", []),
    ("storage_compatibility_mode: UPGRADING\n", "storage_compatibility_mode: NONE\n", []),
    ("storage_compatibility_mode: NONE\n", "storage_compatibility_mode: NONE\n", []),
    ("storage_compatibility_mode: CASSANDRA_4\n", "storage_compatibility_mode: NONE\n",
     ["storage_compatibility_mode: CASSANDRA_4 -> NONE"]),
    ("storage_compatibility_mode: NONE\n", "storage_compatibility_mode: UPGRADING\n",
     ["storage_compatibility_mode: NONE -> UPGRADING"]),
    # absent: CASSANDRA_4 for 5.0, to be written as such first
    ("num_tokens: 16\n", "storage_compatibility_mode: CASSANDRA_4\n", []),
    ("num_tokens: 16\n", "storage_compatibility_mode: UPGRADING\n", ["storage_compatibility_mode: CASSANDRA_4 -> UPGRADING"]),
    ("num_tokens: 16\n", "storage_compatibility_mode: NONE\n", ["storage_compatibility_mode: CASSANDRA_4 -> NONE"]),
    ("num_tokens: 16\n", "num_tokens: 16\n", []),  # 4.x: no such key
])
def test_storage_compatibility_mode_steps(tmp_path, live, new, changes):
    num_tokens = "" if "num_tokens" in live else "num_tokens: 16\n"
    assert identity_changes(tmp_path, live + num_tokens, new + ("" if "num_tokens" in new else "num_tokens: 16\n")) == changes


def task_that(name):
    return task(name)["ansible.builtin.assert"]["that"]


@pytest.mark.parametrize("confirm, initialized, diff, ask", [
    ("auto", True, "diff", True), ("auto", False, "diff", False), (True, False, "diff", True), ("true", False, "diff", True),
    ("yes", False, "diff", True), (False, True, "diff", False), ("no", True, "diff", False),
    (True, True, "", False), ("auto", True, "", False),  # nothing changes: nothing to ask
])
def test_confirm_values(confirm, initialized, diff, ask):
    template = task("List the files to change and whether to ask first")["ansible.builtin.set_fact"]["_cassandra_config_ask"]
    assert render(template, cassandra_config_confirm=confirm, _cassandra_config_initialized=initialized,
                  cassandra_config_preview={"results": [{"stdout": diff}]}) is ask


@pytest.mark.parametrize("confirm, valid", [("auto", True), (True, True), ("false", True), ("yes", True), ("always", False),
                                            ("1", False)])
def test_confirm_value_checked(confirm, valid):
    that = task_that("Assert required cassandra_config variables are set")[2]
    assert render("{{ %s }}" % that, cassandra_config_confirm=confirm) is valid


@pytest.mark.parametrize("installed, series, ok", [
    ("", "4.1", True), ("4.1.12", "4.1", True), ("4.1", "4.1", True), ("5.0.9", "4.1", False), ("4.10.1", "4.1", False),
    ("4.0.21", "4.1", False),
])
def test_installed_series(installed, series, ok):
    that = "{{ %s }}" % task_that("Refuse the templates of another series than the one installed")
    assert render(that, _installed=installed, _cassandra_config_series=series) is ok


@pytest.mark.parametrize("services, warn", [
    ({"cassandra.service": {"state": "running"}}, True), ({"cassandra": {"state": "running"}}, True),
    ({"cassandra.service": {"state": "stopped"}}, False), ({}, False),
])
def test_restart_warning_on_a_running_node(services, warn):
    when = task("Warn that a restart is needed")["when"][1]
    assert render("{{ %s }}" % when, ansible_facts={"services": services}) is warn


SEED = task("Seed the alternative conf dir from the one in use")["ansible.builtin.command"]["argv"][2]


def seed(src, dest):
    return subprocess.run(["sh", "-c", SEED, "sh", str(src), str(dest)], stderr=subprocess.PIPE, universal_newlines=True, check=False)


def test_seed_copies_the_dir_in_use(tmp_path):
    # RHEL: the role's conf dir starts as a copy of the one in use, keystores and modes included
    (tmp_path / "prod.conf").mkdir()
    (tmp_path / "prod.conf" / ".keystore").write_text("k")
    (tmp_path / "prod.conf" / ".keystore").chmod(0o400)
    (tmp_path / "new" / "ansible.conf.seed").mkdir(parents=True)  # left by an interrupted run
    (tmp_path / "new" / "ansible.conf.seed" / "stale").write_text("x")
    assert seed(tmp_path / "prod.conf", tmp_path / "new" / "ansible.conf").returncode == 0
    assert sorted(os.listdir(str(tmp_path / "new"))) == ["ansible.conf"]
    assert os.listdir(str(tmp_path / "new" / "ansible.conf")) == [".keystore"]
    assert os.stat(str(tmp_path / "new" / "ansible.conf" / ".keystore")).st_mode & 0o777 == 0o400


def test_seed_parent_created(tmp_path):
    (tmp_path / "prod.conf").mkdir()
    assert seed(tmp_path / "prod.conf", tmp_path / "a" / "b" / "conf").returncode == 0
    assert (tmp_path / "a" / "b" / "conf").is_dir()


def test_seed_refused_when_the_dir_in_use_is_missing(tmp_path):
    # /etc/cassandra/conf pointing to a removed dir: say so, create nothing
    out = seed(tmp_path / "gone", tmp_path / "ansible.conf")
    assert out.returncode == 1 and "conf dir in use (%s) missing" % (tmp_path / "gone") in out.stderr
    assert not (tmp_path / "ansible.conf").exists()
