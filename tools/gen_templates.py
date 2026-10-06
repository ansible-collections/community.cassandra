"""Turn stock Cassandra conf files into cassandra_config templates.

Usage: python3 tools/gen_templates.py <series> <stock_dir> <templates_out_dir> [<5.0 stock cassandra.yaml>]
  e.g. python3 tools/gen_templates.py 4.1 ~/cassandra-4.1.12/conf roles/cassandra_config/templates/4.1 ~/cassandra-5.0.9/conf/cassandra.yaml

Every template starts with a one-line "Managed by Ansible" comment.
Each rule replaces one exact stock line (asserted unique, so an upstream
version that moved/changed it fails loudly). Replacements are inline {{ }}
only, so rendering with the role defaults gives back the stock file.

cassandra.yaml: 5.0's template is the hand-checked reference. Other series
are derived from it by YAML path: same line -> same variable; same key with
another stock value -> same variable, version-dependent default; key unknown
to 5.0 -> new cassandra_<key> variable. Defaults to add are printed.
"""
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER = "Managed by Ansible (community.cassandra.cassandra_config): change the role variables, not this file."


def header(name):
    return "<!-- %s -->" % HEADER if name.endswith(".xml") else "# " + HEADER


REF_SERIES = "5.0"
# Ends every cassandra.yaml template (renders nothing when empty)
EXTRA = """{% if cassandra_extra_settings %}

# Settings no variable covers (cassandra_extra_settings)
{{ cassandra_extra_settings | to_nice_yaml(indent=2) }}{% endif %}"""
REF_TEMPLATE = os.path.join(HERE, "..", "roles", "cassandra_config", "templates", REF_SERIES, "cassandra.yaml.j2")


def opt(var, commented, active, example, off="#"):
    # Commented in stock (with `off`); uncommented with the var's value once it
    # is set, otherwise left as is (stock example value included).
    value = "{{ %s or '%s' }}" % (var, example)
    return (commented, "{{ '' if %s else '%s' }}%s" % (var, off, active.replace("@", value)))


def jvm_var(n):
    # cassandra_jvm<n>_<name> overrides cassandra_jvm_<name>
    def var(name):
        return "(cassandra_jvm%s_%s | default(cassandra_jvm_%s))" % (n, name, name)
    return var


def gc_switch(n, gc, lines):
    # Lines of one GC's block: active when this file's GC is `gc`, commented
    # otherwise. (stock, None) keeps the flag; (stock, name) sets its value
    # from cassandra_jvm_<name>.
    v = jvm_var(n)
    rules = []
    for stock, name in lines:
        flag = stock.lstrip("#")
        on = "'%s'" % flag if name is None else "'%s=' ~ %s" % (flag.split("=")[0], v(name))
        off = stock if stock.startswith("#") else "#" + stock
        rules.append((stock, "{{ %s if %s == '%s' else '%s' }}" % (on, v("gc"), gc, off)))
    return rules


def cms_lines(prefix, parnew=False):
    flags = (["-XX:+UseParNewGC"] if parnew else []) + [
        "-XX:+UseConcMarkSweepGC", "-XX:+CMSParallelRemarkEnabled", "-XX:SurvivorRatio=8",
        "-XX:MaxTenuringThreshold=1", "-XX:CMSInitiatingOccupancyFraction=75", "-XX:+UseCMSInitiatingOccupancyOnly",
        "-XX:CMSWaitDuration=10000", "-XX:+CMSParallelInitialMarkEnabled", "-XX:+CMSEdenChunksRecordAlways",
        "-XX:+CMSClassUnloadingEnabled"]
    return [(prefix + f, "cms_initiating_occupancy_fraction" if "CMSInitiatingOccupancyFraction" in f else None) for f in flags]


G1_50 = [
    ("-XX:+UseG1GC", None), ("-XX:+ParallelRefProcEnabled", None),
    ("-XX:MaxTenuringThreshold=2", "max_tenuring_threshold"), ("-XX:G1HeapRegionSize=16m", "g1_heap_region_size"),
    ("-XX:+UnlockExperimentalVMOptions", None), ("-XX:G1NewSizePercent=50", "g1_new_size_percent"),
    ("-XX:G1RSetUpdatingPauseTimePercent=5", None), ("-XX:MaxGCPauseMillis=300", "max_gc_pause_millis"),
    ("-XX:InitiatingHeapOccupancyPercent=70", "initiating_heap_occupancy_percent"),
]


def g1_lines_4x(pause, tenuring_and_region):
    lines = [("#-XX:+UseG1GC", None), ("#-XX:+ParallelRefProcEnabled", None)]
    if tenuring_and_region:
        lines += [("#-XX:MaxTenuringThreshold=1", "max_tenuring_threshold"),
                  ("#-XX:G1HeapRegionSize=16m", "g1_heap_region_size")]
    return lines + [("#-XX:G1RSetUpdatingPauseTimePercent=5", None),
                    ("#-XX:MaxGCPauseMillis=%s" % pause, "max_gc_pause_millis"),
                    ("#-XX:InitiatingHeapOccupancyPercent=70", "initiating_heap_occupancy_percent")]


def jvm_rules(n, cms, g1):
    return gc_switch(n, "CMS", cms) + gc_switch(n, "G1", g1) + gc_threads_rules(n)


def append_list(var):
    # Suffix for a file's last line: one extra line per list item.
    return "{{ ('\\n' ~ (%s | join('\\n'))) if %s else '' }}" % (var, var)


def last_line(var):
    line = "# The newline in the end of file is intentional"
    return (line, line + append_list(var))


COMMON = {
    "jvm-server.options": [
        ("#-Dcassandra.expiration_date_overflow_policy=REJECT",
         "#-Dcassandra.expiration_date_overflow_policy=REJECT" + append_list("cassandra_jvm_extra_options")),
    ],
    "cassandra-rackdc.properties": [
        ("dc=dc1", "dc={{ cassandra_dc }}"),
        ("rack=rack1", "rack={{ cassandra_rack }}"),
        ("# prefer_local=true", "{{ '' if cassandra_prefer_local else '# ' }}prefer_local=true"),
    ],
    "logback.xml": [
        ('  <root level="INFO">', '  <root level="{{ cassandra_log_level }}">'),
        ('    <appender-ref ref="ASYNCDEBUGLOG" /> <!-- Comment this line to disable debug.log -->',
         "    {{ '' if cassandra_debug_log_enabled else '<!-- ' }}"
         '<appender-ref ref="ASYNCDEBUGLOG" />'
         "{{ '' if cassandra_debug_log_enabled else ' -->' }} <!-- Comment this line to disable debug.log -->"),
        ('  <logger name="org.apache.cassandra" level="DEBUG"/>',
         '  <logger name="org.apache.cassandra" level="{{ cassandra_log_level_cassandra }}"/>'),
        # off by default: under systemd a second copy of system.log in the journal
        ('    <appender-ref ref="STDOUT" />',
         "    {{ '' if cassandra_log_console else '<!-- ' }}<appender-ref ref=\"STDOUT\" />"
         "{{ '' if cassandra_log_console else ' -->' }}"),
    ],
}

ENV_COMMON = [
    # deb and rpm packages ship /var/log/cassandra here, not the tarball's value
    ('    CASSANDRA_LOG_DIR="$CASSANDRA_HOME/logs"', '    CASSANDRA_LOG_DIR={{ cassandra_log_dir }}'),
    opt("cassandra_jmx_rmi_hostname",
        '# JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=<public name>"',
        'JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=@"', "<public name>", off="# "),
    ("    LOCAL_JMX=yes", "    LOCAL_JMX={{ 'yes' if cassandra_local_jmx else 'no' }}"),
    ('JMX_PORT="7199"', 'JMX_PORT="{{ cassandra_jmx_port }}"'),
    # the access file cassandra_jmx_users writes
    ('#JVM_OPTS="$JVM_OPTS -Dcom.sun.management.jmxremote.access.file=/etc/cassandra/jmxremote.access"',
     "{{ '' if cassandra_jmx_users else '#' }}"
     'JVM_OPTS="$JVM_OPTS -Dcom.sun.management.jmxremote.access.file=/etc/cassandra/jmxremote.access"'),
]


def gc_threads_rules(n):
    v = jvm_var(n)
    return [
        opt(v("parallel_gc_threads"), "#-XX:ParallelGCThreads=16", "-XX:ParallelGCThreads=@", "16"),
        opt(v("conc_gc_threads"), "#-XX:ConcGCThreads=16", "-XX:ConcGCThreads=@", "16"),
    ]


def rules_4x(pause, tenuring_and_region):
    # Stock 4.x runs CMS (G1 commented out); heap and young gen set in pairs under CMS
    g1 = g1_lines_4x(pause, tenuring_and_region)
    return dict(COMMON, **{
        "cassandra-env.sh": ENV_COMMON + [
            opt("cassandra_heap_size", '#MAX_HEAP_SIZE="4G"', 'MAX_HEAP_SIZE="@"', "4G"),
            opt("cassandra_heap_newsize", '#HEAP_NEWSIZE="800M"', 'HEAP_NEWSIZE="@"', "800M"),
        ],
        "jvm8-server.options": jvm_rules(8, cms_lines("", parnew=True), g1) + [last_line("cassandra_jvm8_extra_options")],
        "jvm11-server.options": jvm_rules(11, cms_lines(""), g1) + [last_line("cassandra_jvm11_extra_options")],
    })


RULES = {
    "5.0": dict(COMMON, **{
        "cassandra-env.sh": ENV_COMMON + [
            opt("cassandra_heap_size", '#MAX_HEAP_SIZE="20G"', 'MAX_HEAP_SIZE="@"', "20G"),
            opt("cassandra_max_direct_memory_size", '#MAX_DIRECT_MEMORY_SIZE="10G"', 'MAX_DIRECT_MEMORY_SIZE="@"', "10G"),
            ('    CASSANDRA_HEAPDUMP_DIR="$CASSANDRA_LOG_DIR"',
             '    CASSANDRA_HEAPDUMP_DIR="{{ cassandra_heap_dump_dir }}"'),
        ],
        "jvm11-server.options": jvm_rules(11, cms_lines("##"), G1_50) + [last_line("cassandra_jvm11_extra_options")],
        "jvm17-server.options": jvm_rules(17, [], G1_50) + [last_line("cassandra_jvm17_extra_options")],
    }),
    "4.1": rules_4x("300", True),
    "4.0": rules_4x("500", False),
}


def sync_mode(mode, key, var, example=None):
    # A commitlog setting Cassandra accepts in one commitlog_sync mode only:
    # active in that mode, commented out (as in stock) in the others, with the
    # stock example value when the variable has no default
    value = var if example is None else "%s if cassandra_commitlog_sync == '%s' else '%s'" % (var, mode, example)
    return "{{ '' if cassandra_commitlog_sync == '%s' else '# ' }}%s: {{ %s }}" % (mode, key, value)


# cassandra.yaml lines the derivation from 5.0 cannot map (4.0 keys carry the
# unit in their name): applied to the derived template, same as RULES
YAML_RULES = {
    "4.0": [
        ("commitlog_sync_period_in_ms: {{ cassandra_commitlog_sync_period_in_ms }}",
         sync_mode("periodic", "commitlog_sync_period_in_ms", "cassandra_commitlog_sync_period_in_ms")),
        ("# commitlog_sync_group_window_in_ms: 1000",
         sync_mode("group", "commitlog_sync_group_window_in_ms", "cassandra_commitlog_sync_group_window_in_ms", "1000")),
    ],
}


def replace_lines(name, lines, rules):
    for old, new in rules:
        hits = [i for i, line in enumerate(lines) if line == old]
        assert len(hits) == 1, "%s: %r found %d times" % (name, old, len(hits))
        lines[hits[0]] = new


def yaml_paths(lines):
    # One key per line: raw text for comments/blank, YAML path for settings.
    stack, out = [], []  # stack: [indent, key, child item count]
    for line in lines:
        body = line.lstrip()
        if not body or body.startswith("#"):
            # Indented comments repeat across sections (e.g. "  # optional: true")
            out.append("%s\0%s" % (stack[0][1] if stack else "", line) if line.startswith(" ") else line)
            continue
        indent = len(line) - len(body)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if body.startswith("- "):
            parent = stack[-1] if stack else [None, None, 0]
            parent[2] += 1
            stack.append([indent, "[%d]" % parent[2], 0])
            body, indent = body[2:], indent + 2
        stack.append([indent, body.split(":", 1)[0].strip(), 0])
        out.append(tuple(entry[1] for entry in stack))
    return out


def split_value(line):
    # "key: value  # comment" -> ("key:", "value", "  # comment")
    key, rest = line.split(":", 1) if ":" in line else (line, "")
    m = re.match(r"\s*(.*?)(\s+#.*|\s*)$", rest)
    return key + ":", m.group(1), m.group(2)


def value_expr(value, var):
    for q in ("'", '"'):
        if len(value) > 1 and value[0] == q == value[-1]:
            return "%s{{ %s }}%s" % (q, var, q), value[1:-1]
    parsed = yaml.safe_load(value)
    if isinstance(parsed, bool):
        return "{{ %s | lower }}" % var, parsed
    return "{{ %s }}" % var, parsed


# Nested keys named like their 5.0 siblings (cassandra_server_keystore, ...)
RENAMES = {
    "server_encryption_options_keystore_password": "server_keystore_password",
    "server_encryption_options_truststore_password": "truststore_password",
    "client_encryption_options_keystore_password": "client_keystore_password",
    "server_encryption_options_enable_legacy_ssl_storage_port": "enable_legacy_ssl_storage_port",
}


def quote_secret(line):
    # A password may hold any character: quoted in YAML unless it reads as a plain string
    m = re.match(r"^(.*password: )\{\{ (.*) \}\}$", line)
    if not m or "_cassandra_config_quote" in line:
        return line
    return "%s{{ (%s) | regex_replace(\"'\", \"''\") | regex_replace(_cassandra_config_quote, \"'\\\\1'\") }}" % m.groups()


def derive_yaml(ref_stock, ref_tpl, stock):
    ref = {}
    for key, a, b in zip(yaml_paths(ref_stock), ref_stock, ref_tpl):
        if a != b:
            assert key not in ref, "ambiguous reference line: %r" % a
            ref[key] = (a, b)
    known = set(yaml_paths(ref_stock))
    out, new_vars, conflicts = [], {}, {}
    for key, line in zip(yaml_paths(stock), stock):
        if key in ref:
            a, b = ref[key]
            if not isinstance(key, tuple):
                out.append(b)
                continue
            # Same setting, indentation may differ: keep the variable
            prefix, value, suffix = split_value(line)
            if value == split_value(a)[1]:
                out.append(line[:len(line) - len(line.lstrip())] + b.lstrip())
                continue
            var = re.search(r"cassandra_\w+", b).group(0)
            expr, default = value_expr(value, var)
            out.append("%s %s%s" % (prefix, expr, suffix))
            conflicts[var] = default
        elif isinstance(key, tuple) and key not in known and split_value(line)[1]:
            prefix, value, suffix = split_value(line)
            name = "_".join(k for k in key if not k.startswith("["))
            var = "cassandra_" + RENAMES.get(name, name)
            expr, default = value_expr(value, var)
            out.append("%s %s%s" % (prefix, expr, suffix))
            new_vars[var] = default
        else:
            out.append(line)
    return [quote_secret(line) for line in out], new_vars, conflicts


def main(series, stock_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, rules in RULES[series].items():
        with open(os.path.join(stock_dir, name)) as f:
            lines = f.read().split("\n")
        replace_lines(name, lines, rules)
        with open(os.path.join(out_dir, name + ".j2"), "w") as f:
            f.write("\n".join([header(name)] + lines))

    if series != REF_SERIES:
        ref_stock = sys.argv[4] if len(sys.argv) > 4 else None
        assert ref_stock, "deriving cassandra.yaml needs the %s stock cassandra.yaml as 4th argument" % REF_SERIES
        with open(ref_stock) as a, open(REF_TEMPLATE) as b, open(os.path.join(stock_dir, "cassandra.yaml")) as c:
            ref_tpl = b.read()
            assert ref_tpl.endswith(EXTRA), "reference template must end with the extra settings block"
            ref_tpl = ref_tpl[:-len(EXTRA)].split("\n")
            assert ref_tpl[0] == header("cassandra.yaml"), "reference template must start with the header"
            lines, new_vars, conflicts = derive_yaml(a.read().split("\n"), ref_tpl[1:], c.read().split("\n"))
        replace_lines("cassandra.yaml", lines, YAML_RULES.get(series, []))
        with open(os.path.join(out_dir, "cassandra.yaml.j2"), "w") as f:
            f.write("\n".join([header("cassandra.yaml")] + lines) + EXTRA)
        print("# %s: new variables" % series)
        print(yaml.safe_dump(new_vars, sort_keys=False) if new_vars else "{}")
        print("# %s: stock value differs from %s for" % (series, REF_SERIES))
        print(yaml.safe_dump(conflicts, sort_keys=False) if conflicts else "{}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
