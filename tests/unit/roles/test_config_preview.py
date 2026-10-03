from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

# cassandra_config shows what it would change (secrets masked), asks before
# changing an initialized node and refuses to change the identity of a joined node.

import base64
import json
import os
import subprocess
import sys
import time

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


def task_vars(t, **variables):
    """The variables of a task, its own vars rendered in order on top."""
    templated = {k: v for k, v in t.get("vars", {}).items() if isinstance(v, str) and "{{" in v}
    variables.update({k: v for k, v in t.get("vars", {}).items() if k not in templated})
    for name, value in templated.items():  # in the order they use each other
        variables[name] = render(value, **variables)
    return variables


def live_paths(text):
    """_cassandra_config_live_paths for a live cassandra.yaml (text or bytes; None: none)."""
    t = task("List the absolute paths of the live cassandra.yaml")
    live = {} if text is None else {"content": base64.b64encode(text if isinstance(text, bytes) else text.encode()).decode()}
    v = task_vars(t, cassandra_config_live=live)
    return render(t["ansible.builtin.set_fact"]["_cassandra_config_live_paths"], **v)


INVENTORY = dict(inventory_hostname="node1", cassandra_data_file_directories=["/var/lib/cassandra/data"],
                 cassandra_extra_settings={}, cassandra_conf_dir="/etc/cassandra",
                 _cassandra_config_default_data_dir="/var/lib/cassandra/data",
                 cassandra_commitlog_dir="/var/lib/cassandra/commitlog", cassandra_saved_caches_dir="/var/lib/cassandra/saved_caches",
                 cassandra_hints_dir="/var/lib/cassandra/hints")


def stat_result(d, isdir):
    """What the stat loop registers for a candidate (failed_when: false: an error leaves no stat)."""
    try:
        exists = isdir(d + "/system")
    except OSError as e:
        return {"item": d, "failed": False, "msg": e.strerror}  # what stat returns, in English (LC_ALL=C)
    return {"item": d, "stat": {"exists": exists, "isdir": exists}}


def initialized_facts(live=None, readable=True, isdir=os.path.isdir, services=None, **inventory):
    """The facts of "Tell whether this node was already initialized": the role's templates, the modules simulated."""
    v = dict(INVENTORY, **inventory)
    v["cassandra_config_live_stat"] = {"stat": {"exists": live is not None}}
    v["cassandra_config_live"] = {"content": base64.b64encode(live.encode()).decode()} if live is not None and readable else {}
    v["_cassandra_config_live_paths"] = live_paths(live if readable else None)
    items = render(task("Look for the system keyspace of an initialized node")["loop"], **v)
    v["cassandra_config_system"] = {"results": [stat_result(d, isdir) for d in items]}
    v["ansible_facts"] = {"services": services or {}}
    t = task("Tell whether this node was already initialized")
    v = task_vars(t, **v)
    return {k: render(val, **v) for k, val in t["ansible.builtin.set_fact"].items()}


def found_in(tmp_path, live, inventory_dirs, system_in):
    """Where the node was found initialized, dirs relative to tmp_path."""
    for d in system_in:
        (tmp_path / d / "system").mkdir(parents=True)
    (tmp_path / "conf").mkdir()
    root = str(tmp_path) + "/"
    facts = initialized_facts(None if live is None else live.replace("@", root),
                              cassandra_data_file_directories=[root + d for d in inventory_dirs],
                              _cassandra_config_default_data_dir=root + "default", cassandra_conf_dir=root + "conf")
    return [w.replace(root, "").replace("/system", "") for w in facts["_cassandra_config_initialized_why"].split(", ") if w]


@pytest.mark.parametrize("live, inventory_dirs, system_in, found", [
    (None, ["d1", "d2"], [], []),  # no live cassandra.yaml
    (None, ["d1", "d2"], ["d2"], ["d2"]),  # JBOD reordered in the inventory
    (None, ["d1"], ["default"], ["default"]),  # the package's default data dir
    (None, ["d1"], ["data/data"], ["data/data"]),  # a tarball's
    # the inventory does not match the node yet: its live cassandra.yaml does
    ("data_file_directories:\n    - @old1  # disk 1\n    - '@old2'\ncommitlog_directory: x\n", ["d1"], ["old2"], ["old2"]),
    ("data_file_directories: # JBOD\n    - @old1\n", ["d1"], ["old1"], ["old1"]),
    ("local_system_data_file_directory: \"@sys\"\n", ["d1"], ["sys"], ["sys"]),
    ("data_file_directories:\n- @old1\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories: [@old0, '@old1']\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories: [\n  @old0,\n  @old1 ]\nnum_tokens: 16\n", ["d1"], ["old1"], ["old1"]),
    ('"data_file_directories" :\n  - &a @old1\n', ["d1"], ["old1"], ["old1"]),
    ("\ufeffdata_file_directories:\n  -\n    @old1\n", ["d1"], ["old1"], ["old1"]),
    ("data_file_directories:\n  - @h#1\n", ["d1"], ["h#1"], ["h#1"]),
    ("data_file_directories:\n  - '@sp ace'\n", ["d1"], ["sp ace"], ["sp ace"]),
    ('data_file_directories:\n  - "@sp ace # x"\n', ["d1"], ["sp ace # x"], ["sp ace # x"]),
    ("data_file_directories:\n  - @caf\xe9\n", ["d1"], ["caf\xe9"], ["caf\xe9"]),
    ("data_file_directories:\n  - @d1/\n", [], ["d1"], ["d1"]),  # a trailing slash
    ("data_file_directories:\n  - @d1\r\n  - @d2\r\n", [], ["d2"], ["d2"]),  # CRLF
    ("hints_directory: @old1  # any key\n", ["d1"], ["old1"], ["old1"]),
    ("cluster_name: 'x'  # see @old1\n", ["d1"], ["old1"], ["old1"]),  # an inline comment
    # comment lines are not read by Cassandra
    ("# data_file_directories:\n#     - @old1\n", ["d1"], ["old1"], []),
    ("cluster_name: 'x'\n", ["d1"], ["old1"], []),
    # the package's file of a new node: its data dir not created yet
    ("data_file_directories:\n    - @var/lib/cassandra/data\n", ["d1"], [], []),
])
def test_initialized_node_found(tmp_path, live, inventory_dirs, system_in, found):
    assert found_in(tmp_path, live, inventory_dirs, system_in) == found


def test_stock_package_files_list_their_dirs():
    stock = "# data_file_directories:\n#   - /x\ndata_file_directories:\n    - /var/lib/cassandra/data\n" \
            "commitlog_directory: /var/lib/cassandra/commitlog\n# see https://cassandra.apache.org/doc/ and 1/4 of heap\n"
    assert live_paths(stock) == ["/var/lib/cassandra/data", "/var/lib/cassandra/commitlog"]


@pytest.mark.parametrize("text", ["data_file_directories: ['/x{{ 7 * 6 }}', /old]\n", "data_file_directories: [/x{%raw%}, /old]\n"])
def test_live_path_with_a_brace_never_kept(text):
    assert live_paths(text) == ["/old", "{"]
    facts = initialized_facts(text, isdir=lambda d: d == "/old/system")
    assert facts["_cassandra_config_initialized"] is True
    assert facts["_cassandra_config_initialized_why"] == '/old/system, a path with "{" in the live cassandra.yaml'


@pytest.mark.parametrize("name", ["Read the live cassandra.yaml", "List the absolute paths of the live cassandra.yaml",
                                  "Look for the system keyspace of an initialized node"])
def test_live_file_never_shown(name):
    # a secret, or a PEM key line, may start with "/"
    assert task(name)["no_log"] is True


def test_long_lines_are_fast_and_skipped():
    start = time.time()
    paths = live_paths("k: /" + " " * 100000 + "x\nk: /" + "a " * 200 + "\n- /" + "b" * 300 + "\n- /ok\n")
    assert time.time() - start < 5
    assert "/ok" in paths and not [p for p in paths if max(len(c) for c in p.split("/")) > 255]


@pytest.mark.parametrize("text, path", [
    ("data_file_directories:\n  - /data/my disk  # disk 1\n", "/data/my disk"),  # a plain path with a space
    ("local_system_data_file_directory: /data/my sys\n", "/data/my sys"),
])
def test_plain_path_with_spaces(text, path):
    assert path in live_paths(text)


def test_live_file_not_readable():
    facts = initialized_facts("data_file_directories: [/x]\n", readable=False, isdir=lambda d: False)
    assert facts["_cassandra_config_initialized"] is True
    assert facts["_cassandra_config_initialized_why"] == "the live cassandra.yaml not readable"
    assert facts["_cassandra_config_reset"] == ""  # nothing found to empty


@pytest.mark.parametrize("extra, local", [({"local_system_data_file_directory": "/sys"}, ["/sys"]), ({}, []),
                                          ({"local_system_data_file_directory": None}, [])])
def test_candidate_dirs(extra, local):
    items = render(task("Look for the system keyspace of an initialized node")["loop"], cassandra_data_file_directories=["/d1/"],
                   cassandra_extra_settings=extra, cassandra_conf_dir="/opt/c/conf", _cassandra_config_default_data_dir="/var/lib/cassandra/data",
                   _cassandra_config_live_paths=["/d1", "{"])
    assert items == ["/d1"] + local + ["/var/lib/cassandra/data", "/opt/c/data/data"]


@pytest.mark.parametrize("found, name, service, initialized, why", [
    (["/data"], "cassandra.service", "stopped", True, "/data/system"),
    ([], "cassandra.service", "running", True, "Cassandra is running"),
    ([], "cassandra", "running", True, "Cassandra is running"),  # a sysv init script, no systemd
    (["/d1", "/d2"], "cassandra.service", "running", True, "/d1/system, /d2/system, Cassandra is running"),
    ([], "cassandra.service", "stopped", False, ""), ([], None, None, False, ""),
])
def test_initialized_when_system_found_or_running(found, name, service, initialized, why):
    facts = initialized_facts(None, isdir=lambda d: d[:-len("/system")] in found, services={name: {"state": service}} if name else {},
                              cassandra_data_file_directories=["/d1", "/d2", "/data"])
    assert facts["_cassandra_config_initialized"] is initialized
    assert facts["_cassandra_config_initialized_why"] == why


def raising(errno_, path):
    def isdir(d):
        if d == path + "/system":
            raise OSError(errno_, os.strerror(errno_), d)
        return False
    return isdir


@pytest.mark.parametrize("errno_, initialized", [
    (20, False),  # a file (a keystore path): not a data dir
    (36, False),  # a name too long to exist
    (13, True),  # permission denied: not checked
    (40, True),  # too many symlinks: not checked
])
def test_stat_errors(errno_, initialized):
    assert task("Look for the system keyspace of an initialized node")["environment"] == {"LC_ALL": "C"}
    facts = initialized_facts("data_file_directories: [/x]\n", isdir=raising(errno_, "/x"))
    assert facts["_cassandra_config_initialized"] is initialized
    assert facts["_cassandra_config_initialized_why"] == ("a data dir that could not be checked" if initialized else "")


def test_reset_hint_lists_the_dirs():
    facts = initialized_facts("data_file_directories: [/old/data]\n", isdir=lambda d: d == "/old/data/system",
                              cassandra_data_file_directories=["/new/data"], cassandra_commitlog_dir="/cl",
                              cassandra_saved_caches_dir="/sc", cassandra_hints_dir="/h")
    assert facts["_cassandra_config_reset"] == (
        "ONLY if this node never joined the real cluster (e.g. started once with the stock config), it can start over, "
        "which DELETES its data: stop Cassandra, check these are this node's dirs (not another instance's) and empty "
        "them: /old/data, /new/data, /cl, /sc, /h, then run again.")


def test_no_reset_hint_when_only_running():
    facts = initialized_facts(None, isdir=lambda d: False, services={"cassandra.service": {"state": "running"}})
    assert facts["_cassandra_config_initialized"] is True and facts["_cassandra_config_reset"] == ""


def refusal(task_name, **variables):
    t = task(task_name)
    return render(t["ansible.builtin.assert"]["fail_msg"], **task_vars(t, **variables))


def test_identity_refusal_says_where_and_how_to_reset():
    msg = refusal("Refuse to change the identity of a joined node", inventory_hostname="node1",
                  cassandra_config_identity={"stdout": '["cluster_name: Test Cluster -> Prod"]'},
                  _cassandra_config_initialized_why="/var/lib/cassandra/data/system", _cassandra_config_reset="RESET-HINT.")
    assert msg.startswith("node1 was already initialized (/var/lib/cassandra/data/system) and these settings would change: "
                          "cluster_name: Test Cluster -> Prod. A node keeps them for life: ")
    assert msg.endswith("set cassandra_config_force_identity_change: true. RESET-HINT.")


@pytest.mark.parametrize("initialized, expected", [
    (True, "Config changes not confirmed on node1 (already initialized: Cassandra is running). Run interactively"
           " and answer 'yes', or set cassandra_config_confirm: false to apply without asking."),
    (False, "Config changes not confirmed on node1. Run interactively"
            " and answer 'yes', or set cassandra_config_confirm: false to apply without asking."),
])
def test_confirmation_refusal_says_where(initialized, expected):
    # no reset hint there: a node whose change was only declined
    assert refusal("Stop unless the changes were confirmed", inventory_hostname="node1", _cassandra_config_initialized=initialized,
                   _cassandra_config_initialized_why="Cassandra is running", _cassandra_config_reset="RESET-HINT.") == expected


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
