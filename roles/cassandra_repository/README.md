cassandra_repository
====================

Configures a repository for Cassandra on Debian and RedHat based platforms.

Requirements
------------

ansible-core 2.15 or later (the apt repository is written with
`ansible.builtin.deb822_repository`), and GnuPG 2.2.8 or later on the node
(`gpg --show-keys`, to check the signing keys): EL7 and Amazon Linux 2 are
not supported.

Role Variables
--------------

cassandra_version:
  - Which version of Cassandra to install, e.g. "50x", "41x", "40x".
  - Default "50x". cassandra_install reads it too: set it for both (e.g. in
    group_vars), not as a parameter of this role only.
  - See the distribution names available at:
      - https://debian.cassandra.apache.org (Debian & Ubuntu)
      - https://redhat.cassandra.apache.org/ (RedHat)

cassandra_repository_key_url:
  - Where the release signing keys are downloaded from. Default
    https://downloads.apache.org/cassandra/KEYS.
  - Every key the file holds must be listed in
    `cassandra_repository_key_fingerprints` (primary key fingerprints; the
    default lists the keys in the Apache file), or the role fails: when Apache
    adds a release manager's key, check it, then add it to the list.
  - Offline nodes: a local mirror URL, or a copy of the file on the node
    (`file:///path/to/KEYS`).

cassandra_apt_keyring_path / cassandra_rpm_key_path:
  - Where the keys are installed (Debian & Ubuntu / RedHat).

Dependencies
------------

A list of other roles hosted on Galaxy should go here, plus any details in
regards to parameters that may need to be set for other roles, or variables that
are used from other roles.

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables
passed in as parameters) is always nice for users too:

    - hosts: servers
      roles:
         - { role: cassandra_repository, x: 42 }

License
-------

BSD

Author Information
------------------

An optional section for the role authors to include contact information, or a
website (HTML is not allowed).
