cassandra_install
=================

Installs Apache Cassandra from the repository set up by `cassandra_repository`,
with the Java version the series is built for.

On Debian/Ubuntu, the package would start Cassandra with its stock config as
soon as it is installed; a temporary `policy-rc.d` prevents that, so the node
only starts once it is configured.

Role Variables
--------------

* `cassandra_version`: Cassandra series, same values as `cassandra_repository`
  (`40x`, `41x`, `50x`). Default `50x`.
* `cassandra_java_version`: Java installed before Cassandra. Defaults to the
  series' version from `cassandra_java_versions` (11 for 4.x, 17 for 5.0).
  Debian 12 and later have no Java 11 package (Ubuntu 22.04 and 24.04 do):
  for 4.x there, add a repository that has one (e.g. Adoptium) and set
  `cassandra_java_package` (e.g. `temurin-11-jdk`). The role checks the
  package is available before installing anything.
* `cassandra_java_package`: package name, derived from the OS and
  `cassandra_java_version`.
* `cassandra_cqlsh_python`: Python used by cqlsh. Empty (default): `python3`,
  unless it is outside the range the series' cqlsh supports
  (`cassandra_cqlsh_python_supported`: 3.6-3.11 for 4.x, 3.8-3.13 for 5.0);
  then `python3.11` is installed next to it and cqlsh is pointed at it
  (`/usr/local/bin/cqlsh` wrapper, `CQLSH_PYTHON` in `/etc/profile.d`).
  The system `python3` is never changed. When no longer needed, these files
  are removed, only if the role wrote them.
* `cassandra_cqlsh_python_repo_uri`: where python3.11 comes from on Ubuntu
  releases that don't ship it (default: the deadsnakes PPA, signed by the key
  shipped in `files/deadsnakes.asc`; empty to rely on the configured
  repositories).

Packages installed: `cassandra` and `cassandra-tools` (`cassandra_packages`,
set per OS family in `vars/`).

jemalloc is installed when available (Debian/Ubuntu, and RHEL-family with EPEL
or Amazon Linux).

Example Playbook
----------------

    - hosts: cassandra
      roles:
        - community.cassandra.cassandra_repository
        - community.cassandra.cassandra_install

License
-------

BSD
