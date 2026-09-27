=================================
Community.Cassandra Release Notes
=================================

.. contents:: Topics

v2.0.0
======

Release Summary
---------------

Cassandra 5.0 officially supported.

Minor Changes
-------------

- cassandra_role - (#328) 5.0's Dynamic Data Masking adds 2 implicit permissions (UNMASK, SELECT_MASKED). Test now expects the right row count per version instead of a hardcoded one.
- cassandra_verify - (#328) extended the existing 4.1 "verify disabled by default" test skip to 50x (same restriction applies).

Bugfixes
--------

- cassandra_linux - (#328) fixed ansible.builtin.mount resolution, added missing ansible.posix dependency.
- cassandra_repository - (#328) apt key handling modernized to signed-by keyring (the old apt_key approach fails GPG verification for the 50x repo).
- cassandra_status - (#331,#332) various bugfixes and enhancements.
- cassandra_streamthroughput / cassandra_interdcstreamthroughput - (#328) fixed a pre-existing bug (present since 4.1) where the -d flag never actually reached nodetool, causing both to fail on 4.1+/5.0.

v1.5.2
======

Release Summary
---------------

Adds two new modules.

New Modules
-----------

- community.cassandra.cassandra_statusbinary - Returns the status of the binary protocol, also known as the native transport (#324).
- community.cassandra.cassandra_statusgossip - Returns the status of gossip (#324).

v1.5.1
======

Release Summary
---------------

Maintenance release.

Minor Changes
-------------

- Update RETURN documentation block in the cassandra_status to describe return data correctly (#323).

v1.5.0
======

Release Summary
---------------

New features in cassandra_status module.

Minor Changes
-------------

- cassandra_status - Adds resolve_ip and keyspace parameters and provides richer return data (#316).

v1.4.1
======

Release Summary
---------------

Maintenance release.

Minor Changes
-------------

- 306 - various roles - Use full module paths.

v1.4.0
======

Release Summary
---------------

Maintenance release.

Minor Changes
-------------

- 287 - Adds the consistency_level parameter to the cassandra_role, cassandra_keyspace and cassandra_table modules.

v1.3.3
======

Release Summary
---------------

Maintenance release. Version bumped to get the auto-release running.

v1.3.2
======

Release Summary
---------------

Maintenance release

Minor Changes
-------------

- 274 - cassandra_keyspace & cassandra_role - Ensure that data_centres parameter and aliases are consistent.

v1.3.1
======

Release Summary
---------------

Maintenance release

Minor Changes
-------------

- 269 - cassandra_role - Allow for update of passwords.

Bugfixes
--------

- 258 - cassandra_repository - Add static key.
- 259 - cassandra_repository - Fix repo url.

v1.3.0
======

Release Summary
---------------

Maintenance release

Minor Changes
-------------

- 230 - Adds basic SSL/TLS support to the cassandra_keyspace, cassandra_role and cassandra_table modules.

v1.2.4
======

Release Summary
---------------

Maintenance release

Bugfixes
--------

- 244 cassandra_repository - Update APT Repository url.

v1.2.3
======

Release Summary
---------------

Maintenance release

Bugfixes
--------

- 239 - cassandra_role - Adds quoting to role name to support special characters in the role name, i.e. my-app-role.

v1.2.2
======

Release Summary
---------------

Maintenance release

Bugfixes
--------

- 213 - cassandra_cqlsh - Missing handler for `--ssl` option for `cassandra_cqlsh`
- 214 - cassandra_fullquerylog - Fix typo in documentation.

v1.2.0
======

Release Summary
---------------

Adds many new modules and a minor bug fix.

Bugfixes
--------

- 204 - Fix cassandra_role keyspace idempotency bug.

New Modules
-----------

- community.cassandra.cassandra_assassinate - Run the assassinate command against a node.
- community.cassandra.cassandra_batchlogreplaythrottle - Sets the batch log replay throttle.
- community.cassandra.cassandra_compact - Manage compaction on the Cassandra node.
- community.cassandra.cassandra_concurrency - Manage concurrency parameters on the Cassandra node.
- community.cassandra.cassandra_decommission - Deactivates a node by streaming its data to another node.
- community.cassandra.cassandra_fullquerylog - Manages the full query log feature.
- community.cassandra.cassandra_garbagecollect - Removes deleted data from one or more tables.
- community.cassandra.cassandra_invalidatecache - Invalidates the various caches on the Cassandra node.
- community.cassandra.cassandra_maxhintwindow - Set the specified max hint window in ms.
- community.cassandra.cassandra_removenode - Removes a node by the given host id from the cluster.
- community.cassandra.cassandra_timeout - Manages the timeout on the Cassandra node.
- community.cassandra.cassandra_truncatehints - Truncate all hints on the local node, or truncate hints for the endpoint(s) specified.

v1.1.0
======

Release Summary
---------------

Adds new module cassandra_reload and provides a few minor fixes.

Minor Changes
-------------

- 182 - Add retries to network related tasks in all roles.
- 183 - Adds new module cassandra_reload.
- A bunch of other PRs addressed issues in the integration test code related to Cassandra 4.0.

v1.0.6
======

Release Summary
---------------

Maintenance release

Minor Changes
-------------

- Add additional_args parameter to cassandra_cqlsh module PR149.
- Various minor module documentation improvements PR161.

Bugfixes
--------

- Fix import error in cassandra_cqlsh after 311x upgrade - PR158.
- Improve regex in cassandra_keyspace module - PR160.

v1.0.5
======

Release Summary
---------------

Maintenance release

Bugfixes
--------

- Add missing metadata to existing roles.
- Remove cassandra_dba role.

v1.0.4
======

Release Summary
---------------

Maintenance release

Bugfixes
--------

- All modules - Ensure login parameters are available across all modules.
- cassandra_cqlsh - Double quote cql shell command when it contains single quotes.
