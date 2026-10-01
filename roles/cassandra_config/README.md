cassandra_config
================

Templates Cassandra's configuration files, with the settings exposed as
variables whose defaults are the stock values.

Files: `cassandra.yaml`, `cassandra-env.sh`, `jvm-server.options`,
`jvm<N>-server.options` (`jvm11`/`jvm17` for 5.0, `jvm8`/`jvm11` for 4.x),
`cassandra-rackdc.properties` and `logback.xml`, for Cassandra 4.0, 4.1 and
5.0 (stock files of 4.0.21, 4.1.12 and 5.0.9). The series is picked with
`cassandra_version`.

The templates are the stock files with the settings replaced by variables,
comments included. Rendered with the defaults, they give back the stock files
(checked by the tests), except for the few values the deb/rpm packages change
themselves (data directories, log directory).

Changing an existing node
-------------------------

Every run first renders the files into a temp dir on the node and shows a
`diff -u` against the live files (Ansible's own `--diff` skips files over
100KB, like the 5.0 `cassandra.yaml`). Settings you did not set as
variables are rendered with their stock value, so a hand-edited node shows
here what would be reverted.

With `cassandra_config_confirm: auto` (default), a node that was already
initialized (a `system` keyspace in `cassandra_data_file_directories`, in
the data directories or `local_system_data_file_directory` of its live
`cassandra.yaml` (`/var/lib/cassandra/data` when it sets none; a value it
cannot read for sure counts as initialized), or Cassandra running) is only changed after you
type `yes` at a single prompt listing every host and file concerned; a
first install is not blocked. `true` asks whenever a file changes, `false`
never does. The JMX users files are written without that preview. With
no terminal to answer (CI, AWX), a required confirmation fails the run.
`--check` shows the diff and runs the checks below, and changes nothing. The role never restarts
Cassandra: when it changed files of a running node, it says so.

Values of keys named like `*password*` or `*secret*` are shown as `****` in
that diff, and Ansible's own `--diff` is off for these files. The files are
written owned by root, group `cassandra_group`, mode `0640`
(`cassandra_config_owner`, `cassandra_config_group`, `cassandra_config_mode`):
Cassandra reads them but cannot rewrite them, and `cassandra.yaml` may hold
keystore passwords.

On a node that already joined a cluster, the role refuses to change
`cluster_name`, `num_tokens`, `initial_token`, `partitioner`,
`endpoint_snitch`, `dc`, `rack`, `dc_suffix` or `ec2_naming_scheme`: a new
cluster name, partitioner or `num_tokens` stops the node from starting, a
new dc or rack too (unless forced), a new snitch or forced dc/rack moves
data ownership without streaming it, a new `initial_token` is ignored.
On 5.0, `storage_compatibility_mode` only moves one step at a time,
`CASSANDRA_4` (also when the live file does not set it: write it first),
then `UPGRADING`, then `NONE`, each once the whole cluster runs the previous
one; never back. The error lists the live and new values: fix the inventory to match the node, or
set `cassandra_config_force_identity_change: true` while following a
documented procedure (e.g. a snitch migration); it skips all these checks,
the storage compatibility steps included.

The data, commitlog, hints, saved caches and log directories that don't
exist yet are created, owned by `cassandra_user`:`cassandra_group`, mode
`0750` (missing parents root-owned, `0755`). The role stops first when one
of them is on a mount point of `/etc/fstab` that is not mounted: it would be
on the filesystem below, and a joined node would look new.

Role Variables
--------------

* `cassandra_version`: Cassandra series, same values as
  `cassandra_repository`. Defaults to `50x`. The role stops when the
  installed Cassandra package is of another series.
* `cassandra_conf_dir`: destination directory for the templated files.
  Defaults to where the package makes Cassandra read its config:
  `/etc/cassandra/conf` on RedHat, `/etc/cassandra` on Debian. Keep the
  default with a package install: the package's `cassandra.in.sh`
  hardcodes that path for Cassandra and its tools, anything else is not read.
* `cassandra_rpm_conf_alternative` (RedHat): conf dir seeded once from the
  one `/etc/cassandra/conf` points to (the package's `default.conf` on a new
  install; on a node already run from another dir, its keystores and other
  files come along, owners and modes kept) and selected with `alternatives`
  (priority `cassandra_rpm_conf_alternative_priority`, 100), so
  `/etc/cassandra/conf` points to it and `default.conf` stays as shipped
  (`rpm -V` clean, package upgrades never touch the live config). Default
  `/etc/cassandra/ansible.conf`; `""` writes into the dir in use instead
  (`default.conf` on a new install; it does not switch back a node already moved to its own dir).
* `cassandra_user`, `cassandra_group` (default `cassandra`): the account
  the Cassandra service runs as and a group it is in (set both together).
  The deb and rpm packages create `cassandra` and their init scripts run
  the service as it; set these only when the service runs as another
  account, which the role does not create and does not set in the service
  unit. They own the directories and JMX files the role creates (existing
  directories are left as they are), and `cassandra_group` is the group of
  the config files. The role stops before writing anything when the account
  does not exist or is not in that group (a group name, not a gid), or when
  `cassandra_config_owner` or `cassandra_config_group` does not exist.
  Other roles of the collection are meant to use the same names.
* `cassandra_data_file_directories`: `data_file_directories`, one per disk
  (JBOD). Defaults to `cassandra_data_dir` alone, which should stay first.
* `cassandra_data_dir`: Cassandra's data directory. Defaults to
  `/var/lib/cassandra/data`.
* `cassandra.yaml`: one variable per active key, named
  `cassandra_<setting name>` (e.g. `cassandra_num_tokens`), see
  `defaults/main.yml`. Keys that only exist in 4.x get their own variables
  (4.0 keeps its pre-4.1 names, e.g. `cassandra_read_request_timeout_in_ms`).
  Where a key's stock value differs by series (the 4.0 cache save periods),
  the default follows `cassandra_version`.
  The directories (`data_file_directories`, `commitlog_directory`,
  `saved_caches_directory`, `hints_directory`) are set from
  `cassandra_data_dir`, `cassandra_commitlog_dir`,
  `cassandra_saved_caches_dir` and `cassandra_hints_dir`.
  One deliberate difference from stock: `cassandra_storage_compatibility_mode`
  defaults to `NONE` (5.0 formats and features, right for a new cluster).
  A cluster upgraded from 4.x must set `CASSANDRA_4`, then move through
  `UPGRADING` to `NONE` with rolling restarts.
* Commit log sync: `cassandra_commitlog_sync` is `periodic` (default),
  `group` or `batch`. Cassandra refuses to start with a sync period outside
  periodic mode, or in group mode without a group window, so the role writes
  `cassandra_commitlog_sync_period` (default `10000ms`) in periodic mode only,
  and `cassandra_commitlog_sync_group_window` in group mode only. Group mode
  needs the window set (no default, as in Cassandra): the longest a write
  waits for the grouped fsync before it is acked. Small values (10-15ms) are
  typical; the stock example, 1000ms, would hold each write up to 1s. Batch
  mode writes neither. 4.0 uses `cassandra_commitlog_sync_period_in_ms` and
  `cassandra_commitlog_sync_group_window_in_ms` (milliseconds, e.g. `15`).
  `commitlog_sync_batch_window_in_ms` has no variable: 4.x does nothing with
  it (and refuses it in periodic mode), 5.0 refuses it.
* `cassandra_jmx_users`: remote JMX users (with `cassandra_local_jmx: false`),
  as `{name, password, access}` (`readwrite`, the default, or
  `readonly`; a `readwrite` user also gets the `create` and `unregister`
  rights of the JDK's controlRole, unless `create_unregister: false`),
  written to `/etc/cassandra/jmxremote.password` and `.access`, mode `0400`
  owned by `cassandra_user`. Keep the passwords in a vault. Without users,
  remote JMX needs a `jmxremote.password` of your own, as in stock.
* `cassandra_config_backup` (default `true`): keep a timestamped copy of
  each file the role replaces, next to it, to roll back.
* `cassandra_extra_settings`: settings no variable covers, as a dict written
  as-is at the end of `cassandra.yaml` (e.g. `{commitlog_total_space: 8192MiB}`).
  Keys the template already has are refused: set them with their variable.
  Cassandra refuses unknown keys at startup.
* `cassandra-env.sh`: `cassandra_log_dir` (defaults to `/var/log/cassandra`,
  as the deb/rpm packages patch it; the tarball's stock value is
  `$CASSANDRA_HOME/logs`), `cassandra_heap_newsize` (4.x only: without G1
  it goes with `cassandra_heap_size`, both or neither; on 5.0 a heap size
  needs G1; the role asserts it),
  `cassandra_heap_size` (empty = stock auto-sizing),
  `cassandra_max_direct_memory_size` and `cassandra_heap_dump_dir` (5.0
  only; on 4.x set `CASSANDRA_HEAPDUMP_DIR` in the service environment),
  `cassandra_local_jmx`, `cassandra_jmx_port`, `cassandra_jmx_rmi_hostname`.
* GC: `cassandra_jvm_gc` defaults to the series' stock GC (`CMS` on 4.x,
  `G1` on 5.0). `G1` on 4.x turns on the stock G1 block with the
  `cassandra_jvm_*` values (5.0's by default); `CMS` needs Java 8/11
  (and on 4.x `cassandra_heap_newsize` with `cassandra_heap_size`); `custom` comments
  out both blocks (set your own flags, e.g. ZGC, with
  `cassandra_jvm<N>_extra_options`). `cassandra_jvm11_gc` etc. override it
  per file; `cassandra_jvm_cms_initiating_occupancy_fraction` tunes CMS.
* `jvm<N>-server.options`: 5.0 G1 settings as
  `cassandra_jvm_<option>` (`max_gc_pause_millis`,
  `initiating_heap_occupancy_percent`, `g1_heap_region_size`,
  `g1_new_size_percent`, `max_tenuring_threshold`, `parallel_gc_threads`,
  `conc_gc_threads`), applied to both files; `cassandra_jvm11_<option>` or
  `cassandra_jvm17_<option>` overrides one file.
  `cassandra_jvm_extra_options` (jvm-server.options),
  `cassandra_jvm8_extra_options`, `cassandra_jvm11_extra_options` and
  `cassandra_jvm17_extra_options` append extra lines.
* TLS / mTLS (`cassandra.yaml`): `cassandra_internode_encryption`,
  `cassandra_server_keystore`, `cassandra_server_keystore_password`,
  `cassandra_truststore`, `cassandra_truststore_password`,
  `cassandra_server_require_client_auth`, `cassandra_server_encryption_optional`,
  `cassandra_server_outbound_keystore` / `_password` (5.0: client certificate
  for outbound internode connections), and on the client side
  `cassandra_client_encryption_enabled`, `cassandra_client_keystore`,
  `cassandra_client_keystore_password`, `cassandra_client_require_client_auth`,
  `cassandra_client_encryption_optional`, `cassandra_client_truststore` /
  `_password`. Settings commented out in stock stay commented until set.
* `cassandra-rackdc.properties`: `cassandra_dc`, `cassandra_rack`,
  `cassandra_prefer_local`.
* `logback.xml`: `cassandra_log_level` (root logger),
  `cassandra_log_level_cassandra` (`org.apache.cassandra` logger),
  `cassandra_debug_log_enabled`, `cassandra_log_console` (default `false`:
  no stdout copy of the logs, which under systemd would be a second copy of
  `system.log` in journald; JVM errors before logback starts still go there).

Testing
-------

The molecule scenario renders every file of every series with defaults
only and checks it line for line against the stock files in
`molecule/default/files/stock-<version>/`, then renders them again with
overrides and checks the changed lines.

Adding a Cassandra version
--------------------------

Templates are generated from the stock files by `tools/gen_templates.py`
(repo root), which fails if a line it replaces is missing or duplicated in
the new version. The 5.0 `cassandra.yaml.j2` is the hand-checked reference;
other series derive theirs from it and print the defaults to add:

    python3 tools/gen_templates.py 5.0 <cassandra-5.0.x>/conf roles/cassandra_config/templates/5.0
    python3 tools/gen_templates.py 4.1 <cassandra-4.1.x>/conf roles/cassandra_config/templates/4.1 <cassandra-5.0.x>/conf/cassandra.yaml

A new series also needs its file list in `vars/main.yml`. The full procedure
(stock fixtures, defaults, argument specs, template release) is in
`tools/README.md`.

Dependencies
------------

None. Expects Cassandra to be installed (`cassandra_install`).

Example Playbook
----------------

    - hosts: cassandra
      vars:
        cassandra_version: 50x  # the same series for all the roles
      roles:
        - community.cassandra.cassandra_repository
        - community.cassandra.cassandra_install
        - community.cassandra.cassandra_linux
        - community.cassandra.cassandra_config

Multi-node, with authentication; per-node values go in host_vars:

    # group_vars/cassandra.yml
    cassandra_cluster_name: "Prod Cluster"
    cassandra_seeds: "10.0.0.1:7000,10.0.0.2:7000"
    cassandra_endpoint_snitch: GossipingPropertyFileSnitch
    cassandra_authenticator: PasswordAuthenticator
    cassandra_authorizer: CassandraAuthorizer
    cassandra_heap_size: 8G

    # host_vars/10.0.0.1.yml
    cassandra_listen_address: 10.0.0.1
    cassandra_rpc_address: 10.0.0.1
    cassandra_dc: dc1
    cassandra_rack: rack1

License
-------

BSD
