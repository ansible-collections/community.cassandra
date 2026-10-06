from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

# cassandra_config refuses Cassandra directories on a mount point of /etc/fstab
# that is not mounted (they would be on the root filesystem).

import os

import pytest
import yaml

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

try:  # ansible-core 2.19+ renders trusted templates only
    from ansible.template import trust_as_template
except ImportError:
    def trust_as_template(template):
        return template

TASKS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "roles", "cassandra_config", "tasks", "main.yml")


def task(name):
    with open(TASKS, encoding="utf-8") as f:
        todo = list(yaml.safe_load(f))
    while todo:
        t = todo.pop(0)
        if t.get("name") == name:
            return t
        todo += t.get("block", []) + t.get("rescue", []) + t.get("always", [])
    raise KeyError(name)


def on_unmounted(dirs, unmounted):
    variables = {
        "cassandra_config_dirs": {"results": [{"item": d, "stat": {"exists": exists}} for d, exists in dirs]},
        "cassandra_config_unmounted": {"stdout_lines": unmounted},
    }
    template = task("Refuse directories on a disk that is not mounted")["vars"]["_on_unmounted"]
    return Templar(loader=DataLoader(), variables=variables).template(trust_as_template(template))


@pytest.mark.parametrize("dirs, unmounted, refused", [
    ([("/data/cassandra/data", False)], ["/data"], ["/data/cassandra/data (/data)"]),
    ([("/data", False)], ["/data"], ["/data (/data)"]),
    # there already: the empty mount point, or dirs left below it on the root filesystem
    ([("/data", True)], ["/data"], ["/data (/data)"]),
    ([("/var/lib/cassandra/data", True), ("/var/lib/cassandra/hints", True)], ["/var/lib/cassandra"],
     ["/var/lib/cassandra/data (/var/lib/cassandra)", "/var/lib/cassandra/hints (/var/lib/cassandra)"]),
    ([("/data/cassandra/data", False)], ["/data2", "/dat"], []),  # not a prefix of a path component
    ([("/data/cassandra/data", False), ("/var/lib/cassandra/hints", True)], [], []),
])
def test_refused_on_unmounted_disk(dirs, unmounted, refused):
    assert on_unmounted(dirs, unmounted) == refused
