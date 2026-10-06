from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

import pytest
import yaml

ROLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "roles")
# roles with an argument spec: every default documented, with the same value
ROLES = sorted(
    role for role in os.listdir(ROLES_DIR)
    if os.path.isfile(os.path.join(ROLES_DIR, role, "defaults", "main.yml"))
    and os.path.isfile(os.path.join(ROLES_DIR, role, "meta", "argument_specs.yml"))
)


def load_yaml(role, path):
    with open(os.path.join(ROLES_DIR, role, path)) as f:
        return yaml.safe_load(f) or {}


def public_defaults(role):
    # _-prefixed variables are internal and not documented
    defaults = load_yaml(role, "defaults/main.yml")
    return dict((k, v) for k, v in defaults.items() if not k.startswith("_"))


def spec_options(role):
    return load_yaml(role, "meta/argument_specs.yml")["argument_specs"]["main"].get("options", {})


def is_templated(value):
    return isinstance(value, str) and "{{" in value


@pytest.mark.parametrize("role", ROLES)
def test_every_default_is_documented(role):
    assert sorted(set(public_defaults(role)) - set(spec_options(role))) == []


@pytest.mark.parametrize("role", ROLES)
def test_documented_options_without_role_default_have_no_spec_default(role):
    # an option can document a variable the role reads but does not set (e.g. set by another role)
    defaults = public_defaults(role)
    options = spec_options(role)
    assert sorted(k for k in options if k not in defaults and "default" in options[k]) == []


@pytest.mark.parametrize("role", ROLES)
def test_spec_defaults_match_role_defaults(role):
    options = spec_options(role)
    mismatches = []
    for name, value in public_defaults(role).items():
        option = options.get(name, {})
        if is_templated(value):
            # computed at run time: the description explains it, a literal default would be wrong
            if "default" in option:
                mismatches.append((name, value, option["default"]))
        elif option.get("default") != value:
            mismatches.append((name, value, option.get("default")))
    assert mismatches == []


@pytest.mark.parametrize("role", ROLES)
def test_descriptions_are_text(role):
    # an unquoted "key: value" in a description is a dict: ansible-doc refuses the whole role
    spec = load_yaml(role, "meta/argument_specs.yml")["argument_specs"]["main"]
    entries = [("main", spec)] + list(spec.get("options", {}).items())
    bad = []
    for name, entry in entries:
        description = entry.get("description", [])
        for line in description if isinstance(description, list) else [description]:
            if not isinstance(line, str):
                bad.append(name)
    assert bad == []


@pytest.mark.parametrize("role", ROLES)
def test_accounts_named_like_cassandra_user(role):
    # accounts are *_user / *_group, like cassandra_user / cassandra_group
    assert sorted(k for k in spec_options(role) if k.endswith(("_owner", "_uid", "_gid"))) == []
