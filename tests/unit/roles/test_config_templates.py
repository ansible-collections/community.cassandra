from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

# cassandra_config templates: the remote JMX users, passwords YAML reads back as
# written, the heap settings cassandra-env.sh accepts, and the service account.

import os
import re

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


def task(name):
    with open(os.path.join(TASKS, "main.yml"), encoding="utf-8") as f:
        todo = list(yaml.safe_load(f))
    while todo:
        t = todo.pop(0)
        if t.get("name") == name:
            return t
        todo += t.get("block", []) + t.get("rescue", []) + t.get("always", [])
    raise KeyError(name)


def render(template, escape_backslashes=True, **variables):
    # escape_backslashes=False: a line of a .j2 file, where Jinja unescapes its string literals itself
    return Templar(loader=DataLoader(), variables=variables).template(trust_as_template(template),
                                                                      escape_backslashes=escape_backslashes)


TEMPLATES = os.path.join(TASKS, "..", "templates")
with open(os.path.join(TEMPLATES, "jmxremote.access.j2"), encoding="utf-8") as f:
    ACCESS = f.read()


@pytest.mark.parametrize("create_unregister, access", [
    (True, "ops readwrite \\\n    create javax.management.monitor.*,javax.management.timer.* \\\n    unregister\nmon readonly\n"),
    (False, "ops readwrite\nmon readonly\n"),
])
def test_jmx_access_rights(create_unregister, access):
    users = [{"name": "ops", "password": "s3cret", "access": "readwrite", "create_unregister": create_unregister},
             {"name": "mon", "password": "m0n", "access": "readonly"}]
    assert render(ACCESS, cassandra_jmx_users=users) == access


with open(os.path.join(TASKS, "..", "vars", "main.yml"), encoding="utf-8") as f:
    ROLE_VARS = yaml.safe_load(f)
with open(os.path.join(TASKS, "..", "templates", "5.0", "cassandra.yaml.j2"), encoding="utf-8") as f:
    TDE_LINE = [line for line in f.read().split("\n") if line.strip().startswith("keystore_password: {{ (cassandra_tde")][0]


@pytest.mark.parametrize("password", [
    "cassandra", "abc #def", "a: b", "@x", "%x", "*x", "!x", "'q'", '"d"', "it's", "yes", "Off", "123", "", "a\\b", "p@ss/w=rd+1",
])
def test_passwords_read_back_as_written(password):
    rendered = render(TDE_LINE, escape_backslashes=False, cassandra_tde_keystore_password=password,
                      _cassandra_config_quote=ROLE_VARS["_cassandra_config_quote"])
    assert yaml.safe_load(rendered) == {"keystore_password": password}


def test_plain_password_stays_as_in_stock():
    assert render(TDE_LINE, escape_backslashes=False, cassandra_tde_keystore_password="cassandra",
                  _cassandra_config_quote=ROLE_VARS["_cassandra_config_quote"]).strip() == "keystore_password: cassandra"


def task_that(name):
    return task(name)["ansible.builtin.assert"]["that"]


@pytest.mark.parametrize("version, gcs, size, newsize, ok", [
    ("41x", ["CMS", "CMS"], "", "", True),
    ("41x", ["CMS", "CMS"], "8G", "800M", True),
    ("41x", ["CMS", "CMS"], "8G", "", False),
    ("41x", ["CMS", "CMS"], "", "800M", False),
    ("41x", ["G1", "custom"], "8G", "", False),  # custom is not G1 for cassandra-env.sh
    ("41x", ["G1", "G1"], "8G", "", True),
    ("50x", ["G1", "G1"], "8G", "", True),
    ("50x", ["CMS", "G1"], "8G", "", False),  # no HEAP_NEWSIZE in 5.0's cassandra-env.sh
    ("50x", ["G1", "custom"], "", "", True),
])
def test_heap_pairs(version, gcs, size, newsize, ok):
    that = "{{ %s }}" % task_that("Assert heap settings are consistent")
    assert render(that, cassandra_version=version, _cassandra_config_gcs=gcs, cassandra_heap_size=size,
                  cassandra_heap_newsize=newsize) is ok


@pytest.mark.parametrize("gcs, ok", [
    (["G1", "CMS"], True),
    (["custom", "G1"], True),
    (["G1", "ZGC"], False),  # a per-file override (cassandra_jvm17_gc) the argument spec does not check
    (["g1", "G1"], False),
])
def test_gc_values(gcs, ok):
    that = [t for t in task_that("Assert required cassandra_config variables are set") if "_cassandra_config_gcs" in t][0]
    assert render("{{ %s }}" % that, _cassandra_config_gcs=gcs) is ok


def owners(tasks):
    # (task, key, value) of every owner, group and become_user, any module, blocks included
    for t in tasks:
        for key, value in t.items():
            if key == "become_user":
                yield t.get("name"), key, value
            elif isinstance(value, dict):
                for k in ("owner", "group"):
                    if k in value:
                        yield t.get("name"), k, value[k]
        for section in ("block", "rescue", "always"):
            yield from owners(t.get(section, []))


ALLOWED = {"owner": {"{{ cassandra_user }}", "{{ cassandra_config_user }}"},
           "group": {"{{ cassandra_group }}", "{{ cassandra_config_group }}"}}


def wrong_owners(tasks):
    return [o for o in owners(tasks) if o[2] not in ALLOWED.get(o[1], set())]


def test_owner_guard_catches_a_hardcoded_account():
    assert wrong_owners([{"name": "a", "file": {"owner": "cassandra"}},
                         {"block": [{"name": "b", "x.y.template": {"group": "{{ cassandra_user }}"}}]},
                         {"name": "c", "command": "id", "become_user": "cassandra"}]) == [
        ("a", "owner", "cassandra"), ("b", "group", "{{ cassandra_user }}"), ("c", "become_user", "cassandra")]


def test_owners_follow_the_service_account():
    # no task hardcodes the cassandra account: cassandra_user/cassandra_group, or the config owner/group variables
    found, wrong = [], []
    for name in sorted(os.listdir(TASKS)):
        with open(os.path.join(TASKS, name), encoding="utf-8") as f:
            tasks = yaml.safe_load(f) or []
        found += list(owners(tasks))
        wrong += wrong_owners(tasks)
        with open(os.path.join(TASKS, name), encoding="utf-8") as f:  # chown, install -o... in a command
            assert re.findall(r"\b(?:chown|chgrp)\b[^\n]*\bcassandra\b|\binstall\b[^\n]*-[og] *cassandra\b", f.read()) == []
    assert found
    assert wrong == []


@pytest.mark.parametrize("user_rc, groups, file_rc, ok", [
    (0, "cassandra", 0, True),
    (0, "dbsvc cassandra", 0, True),  # a supplementary group counts
    (1, "", 0, False),  # no such user
    (0, "dbsvc", 0, False),  # not in cassandra_group
    (0, "cassandra-old", 0, False),  # a group name containing it is not it
    (0, "cassandra", 1, False),  # config owner or group missing
])
def test_account_assert(user_rc, groups, file_rc, ok):
    that = task("Assert the accounts exist")["ansible.builtin.assert"]["that"]
    variables = dict(cassandra_group="cassandra",
                     cassandra_config_service_groups={"rc": user_rc, "stdout": groups},
                     cassandra_config_file_account={"rc": file_rc})
    assert all(render("{{ %s }}" % cond, **variables) for cond in that) is ok


def test_accounts_checked_before_any_write():
    # the account assert comes first in the Configure block (later tasks write or prepare writes),
    # and the JMX users files (access.yml) are written after that block
    with open(os.path.join(TASKS, "main.yml"), encoding="utf-8") as f:
        tasks = yaml.safe_load(f)
    names = [t.get("name") for t in tasks]
    configure = task("Configure")["block"]
    first_write = next(i for i, t in enumerate(configure)
                       if any(isinstance(v, dict) and ("dest" in v or "owner" in v or "state" in v) for v in t.values())
                       or "block" in t or "ansible.builtin.tempfile" in t)
    assert [t["name"] for t in configure].index("Assert the accounts exist") < first_write
    assert all("ansible.builtin.command" in t or "ansible.builtin.assert" in t or "ansible.builtin.stat" in t
               for t in configure[:[t["name"] for t in configure].index("Assert the accounts exist")])
    assert names.index("JMX users") > names.index("Configure")


with open(os.path.join(TASKS, "..", "defaults", "main.yml"), encoding="utf-8") as f:
    ROLE_DEFAULTS = yaml.safe_load(f)


def render_commitlog_lines(series, **overrides):
    # the commitlog_sync lines of the series' cassandra.yaml template, active or commented, rendered
    with open(os.path.join(TEMPLATES, series, "cassandra.yaml.j2"), encoding="utf-8") as f:
        lines = [line for line in f.read().split("\n") if re.match(r"^(# |\{\{[^}]*\}\})?commitlog_sync\w*:", line)]
    variables = dict(ROLE_DEFAULTS, cassandra_version=series.replace(".", "") + "x", **overrides)
    return "\n".join(render(line, escape_backslashes=False, **variables) for line in lines) + "\n"


# Cassandra (DatabaseDescriptor.applySimpleConfig) refuses a sync period outside periodic
# mode and needs a group window in group mode; 4.0 names carry the unit
@pytest.mark.parametrize("series, period, window, overrides", [
    ("5.0", "commitlog_sync_period", "commitlog_sync_group_window", {"cassandra_commitlog_sync_group_window": "15ms"}),
    ("4.1", "commitlog_sync_period", "commitlog_sync_group_window", {"cassandra_commitlog_sync_group_window": "15ms"}),
    ("4.0", "commitlog_sync_period_in_ms", "commitlog_sync_group_window_in_ms",
     {"cassandra_commitlog_sync_group_window_in_ms": 15}),
])
@pytest.mark.parametrize("mode", ["periodic", "group", "batch"])
def test_commitlog_sync_modes(series, period, window, overrides, mode):
    rendered = render_commitlog_lines(series, cassandra_commitlog_sync=mode, **overrides)
    commitlog = yaml.safe_load(rendered)
    expected = {"commitlog_sync": mode}
    if mode == "periodic":
        expected[period] = "10000ms" if series != "4.0" else 10000
    elif mode == "group":
        expected[window] = "15ms" if series != "4.0" else 15
    assert commitlog == expected
    # the line left out stays as the stock comment
    if mode != "periodic":
        assert ("# %s: " % period) in rendered
    if mode != "group":  # with the stock example, the window having no default
        assert ("# %s: %s\n" % (window, "1000" if series == "4.0" else "1000ms")) in rendered


def commitlog_assert(**variables):
    # both commit log asserts, the group window one in group mode only (its `when`)
    variables = dict(dict((k, ROLE_DEFAULTS[k]) for k in ROLE_DEFAULTS if k.startswith("cassandra_commitlog_sync")),
                     _cassandra_config_duration_ms=ROLE_VARS["_cassandra_config_duration_ms"], **variables)
    that = task_that("Assert the commit log sync settings")
    window = task("Assert the commit log group window is set")
    if render("{{ %s }}" % window["when"], **variables):
        that = that + [window["ansible.builtin.assert"]["that"]]
    return all(render("{{ %s }}" % cond, **variables) for cond in that)


@pytest.mark.parametrize("version, mode, settings, ok", [
    ("50x", "periodic", {}, True),
    ("40x", "periodic", {}, True),
    ("50x", "batch", {"cassandra_commitlog_sync_group_window": "0ms", "cassandra_commitlog_sync_period": "0ms"}, True),
    ("50x", "group", {"cassandra_commitlog_sync_group_window": "15ms"}, True),
    ("41x", "group", {"cassandra_commitlog_sync_group_window": "1s"}, True),
    ("50x", "group", {"cassandra_commitlog_sync_group_window": "15ms", "cassandra_commitlog_sync_period": "0ms"},
     True),  # the period is not written in group mode
    ("50x", "group", {}, False),  # no default window, as in Cassandra
    ("41x", "group", {}, False),
    ("40x", "group", {}, False),
    ("50x", "group", {"cassandra_commitlog_sync_group_window": "0ms"}, False),  # Missing value for ..._group_window
    ("41x", "group", {"cassandra_commitlog_sync_group_window": "000ms"}, False),
    ("50x", "group", {"cassandra_commitlog_sync_group_window": "15"}, False),  # a duration needs its unit
    ("50x", "group", {"cassandra_commitlog_sync_group_window": "500us"}, False),  # below the ms min unit
    ("50x", "group", {"cassandra_commitlog_sync_group_window": "15MS"}, False),  # units are lower case
    ("50x", "group", {"cassandra_commitlog_sync_group_window": ""}, False),
    ("50x", "periodic", {"cassandra_commitlog_sync_period": "0ms"}, False),  # Missing value for commitlog_sync_period
    ("41x", "periodic", {"cassandra_commitlog_sync_period": "10000"}, False),
    ("40x", "periodic", {"cassandra_commitlog_sync_period_in_ms": 0}, False),
    ("40x", "group", {"cassandra_commitlog_sync_group_window": "0ms", "cassandra_commitlog_sync_group_window_in_ms": 15}, True),
    ("40x", "group", {"cassandra_commitlog_sync_group_window_in_ms": 0.5}, True),  # 4.0 reads a double
    ("40x", "group", {"cassandra_commitlog_sync_group_window_in_ms": 0}, False),
    ("40x", "group", {"cassandra_commitlog_sync_group_window_in_ms": "15ms"}, False),
    ("50x", "Group", {"cassandra_commitlog_sync_group_window": "15ms"}, False),
    ("50x", "async", {"cassandra_commitlog_sync_group_window": "15ms"}, False),
])
def test_commitlog_sync_assert(version, mode, settings, ok):
    assert commitlog_assert(cassandra_version=version, cassandra_commitlog_sync=mode, **settings) is ok
