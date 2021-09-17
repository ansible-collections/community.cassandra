# Cassandra Collection
![CI](https://github.com/ansible-collections/community.cassandra/workflows/CI/badge.svg)
![CI_roles](https://github.com/ansible-collections/community.cassandra/workflows/CI_roles/badge.svg)
![documentation](https://github.com/ansible-collections/community.cassandra/workflows/documentation/badge.svg)
[![Codecov](https://img.shields.io/codecov/c/github/ansible-collections/community.cassandra)](https://codecov.io/gh/ansible-collections/community.cassandra)
![Build & Publish Collection](https://github.com/ansible-collections/community.cassandra/workflows/Build%20&%20Publish%20Collection/badge.svg)

This collection called `cassandra` aims at providing all Ansible modules allowing to interact with Apache Cassandra.

As this is an independent Collection, it can be released on it's own release cadance.

If you like this collection please give us a rating on [Ansible Galaxy](https://galaxy.ansible.com/community/cassandra).

## Collection contents

### Roles

These roles prepare servers with Debian-based and RHEL-based distributions to run Cassandra.

- `cassandra_firewall`- Manage the firewall on Cassandra nodes.
- `cassandra_install`- Install Cassandra.
- `cassandra_linux`- Configure Linux OS Settings for Cassandra.
- `cassandra_repository`- Configures a package repository for Cassandra on Debian and RedHat based platforms.

#### Modules

- `cassandra_autocompaction`- Enables or disables autocompaction.
- `cassandra_backup`- Enables or disables incremental backup.
- `cassandra_binary`- Enables or disables the binary protocol.
- `cassandra_cleanup`- Runs cleanup on a Cassandra node.
- `cassandra_compactionthreshold`- Sets the compaction threshold.
- `cassandra_compactionthroughput`- Sets the compaction throughput.
- `cassandra_cqlsh`- Run cql commands via the clqsh shell.
- `cassandra_drain`- Drains a Cassandra node.
- `cassandra_flush`- Flushes one or more tables from the memtable to SSTables on disk.
- `cassandra_gossip`- Enables or disables gossip.
- `cassandra_handoff`- Enables or disables the storing of future hints on the current node.
- `cassandra_interdcstreamthroughput`- Sets the inter-dc stream throughput.
- `cassandra_keyspace`- Manage keyspaces on your Cassandra cluster.
- `cassandra_role`- Manage roles on your Cassandra Cluster.
- `cassandra_schema`- Validates the schema version as seen from the node.
- `cassandra_status`- Validates the status of the cluster as seen from the node.
- `cassandra_stopdaemon`- Stops the Cassandra daemon.
- `cassandra_streamthroughput`- Sets the stream throughput.
- `cassandra_table`- Create or drop tables on a Cassandra Keyspace.
- `cassandra_thrift`- Enables or disables the Thrift server.
- `cassandra_traceprobability`- Sets the trace probability.
- `cassandra_upgradesstables`- Upgrade SSTables which are not on the current Cassandra version.
- `cassandra_verify`- Checks the data checksum for one or more tables.

## GitHub workflow

* Maintainers would be members of this GitHub Repo.
* Branch protections could be used to enforce 1 (or 2) reviews from relevant maintainers [CODEOWNERS](.github/CODEOWNERS)

## Contributing

Any contribution is welcome and we only ask contributors to:
* Provide *at least* integration tests for any contribution.
* Create an issues for any significant contribution that would change a large portion of the code base.

## Running integration tests locally

Clone the collection git project. The ansible-test tool requires a specific directory setup to function correctly so please follow carefully.

```
cd && mkdir -p git/ansible_collections/community
git clone https://github.com/ansible-collections/community.cassandra.git ./ansible_collections/community/cassandra
cd ./git/ansible_collections/community/cassandra
```

Create a virtual environment

```
virtualenv venv
source venv/bin/activate
pip install -r requirements-3.6.txt
```

Run all tests

```
ansible-test integration --docker ubuntu1804 -v --color --python 3.6
```

Run tests just for the cassandra_role module

```
ansible-test integration --docker ubuntu1804 -v --color --python 3.6 cassandra_role
```


## License

GNU General Public License v3.0 or later

See LICENCING to see the full text.
