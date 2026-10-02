cassandra_install
=================

Installs Apache Cassandra from the repository set up by `cassandra_repository`,
with the Java version the series is built for, and the DataStax Bulk Loader
(dsbulk) next to the Cassandra tools.

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
* `cassandra_dsbulk_install`: install the DataStax Bulk Loader
  ([dsbulk](https://github.com/datastax/dsbulk)) too. Default `true`. It is
  installed like the tools of the `cassandra-tools` package: unpacked in
  `/usr/share/dsbulk-<version>` (owned by root, read-only for others), with a
  `/usr/share/dsbulk` link to it and `/usr/bin/dsbulk`. It runs with
  `$JAVA_HOME` or the `java` on the `PATH` (the Java installed above, unless
  another one is the default), and writes its logs in `./logs`. The two
  links are taken over; a file or directory in their place (a dsbulk
  installed by other means) stops the role. `false` skips it all (a dsbulk
  already installed is left alone).
* `cassandra_dsbulk_version`: dsbulk release, quoted. Default `"1.11.2"`.
  A version already in `/usr/share` is used as is, not downloaded again; on
  a version change the links move to the new one, then the versions this
  role installed before are removed, as a package upgrade would (a dsbulk
  unpacked in `/usr/share` by other means is left alone; one in the way of
  the version to install, without `bin/dsbulk`, stops the role). Changes
  made in its `conf/` go with it: keep settings in a file of your own,
  passed with `-f`.
* `cassandra_dsbulk_url`: where the tarball comes from. Default: the release
  on GitHub. Or a local mirror
  (e.g. `https://mirror.example.com/dsbulk/dsbulk-1.11.2.tar.gz`), or a copy
  of the file on the node (`file:///path/to/dsbulk-1.11.2.tar.gz`).
* `cassandra_dsbulk_checksum`: checksum of the tarball, as `sha256:<hex>`
  (any form `get_url` takes). The default matches the default version only:
  set it whenever you change the version, or the download is refused. `""`
  skips the check.

Packages installed: `cassandra` and `cassandra-tools` (`cassandra_packages`,
set per OS family in `vars/`).

dsbulk is downloaded from GitHub unless `cassandra_dsbulk_url` points
elsewhere (even `--check` reaches the URL when a download is due): on nodes
without access to it, set that URL or `cassandra_dsbulk_install: false`.

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
