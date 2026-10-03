cassandra_linux
===============

Set Cassandra Linux OS customizations.

Requirements
------------

Any pre-requisites that may not be covered by Ansible itself or the role should
be mentioned here. For instance, if the role uses the EC2 module, it may be a
good idea to mention in this section that the boto package is required.

Role Variables
--------------

* `cassandra_linux_tune_data_disk`: tune the read-ahead and IO scheduler of
  the Cassandra data disk (below). Defaults to `false`: nothing about the
  data disk runs, even when `cassandra_data_dir` is set (e.g. by the
  `cassandra_config` role in the same play).
* `cassandra_data_block_device`: the disk of the Cassandra data, to tune
  when `cassandra_linux_tune_data_disk` is true, e.g. `/dev/sdb` or `/dev/nvme0n1` (a
  partition is taken as its disk). Defaults to `""`: the disk is found from
  `cassandra_data_dir` (the Cassandra data directory, an absolute path, no
  default in this role) with `findmnt` and `lsblk`, once that directory
  exists (before, its disk may not be mounted yet: nothing is tuned): a data directory on
  the root filesystem tunes the root disk. Without either, nothing is
  tuned. LVM, md RAID and dm-crypt volumes are not tuned (a partitioned md
  device is, like a disk): their read-ahead is their own (e.g.
  `lvchange -r`), the role says so. Setting this
  variable to the disk underneath only helps through its scheduler. A device
  set here that can't be tuned fails the role (not in containers, where
  the disk is left alone).
* `cassandra_data_readahead_kb`: read-ahead in KB for that disk
  (`queue/read_ahead_kb`, not `blockdev --setra` sectors). Defaults to `4`,
  the practical minimum: read-ahead brings nothing to Cassandra's random
  reads and fills the page cache with data it doesn't need. The kernel
  rounds it down to whole memory pages (0 with 64 KB pages).
* `cassandra_linux_apply_live`: apply the kernel settings (sysctl, swapoff,
  THP, disk tuning) live, not only persist them. Defaults to `auto`: live
  everywhere except in containers (Ansible's virtualization facts, and
  `cassandra_linux_container_types`), where `/proc/sys` and `/sys` belong to
  the host; what runs at boot (the THP unit, the disk's udev rule) is
  left out there too. Set `true` to tune the host from a dedicated
  privileged container, `false` to only persist (in containers, only the
  files). Ansible doesn't detect
  every container (e.g. Kubernetes pods on cgroup v2): set `false` there,
  the THP unit and the disk's udev rule are then still set up.
* `cassandra_linux_container_types`: `virtualization_type` values taken as
  containers, besides Ansible's own container detection. Defaults to
  `docker`, `podman`, `container`, `containerd`, `lxc`.
* `cassandra_sysfs_block_root`: sysfs directory the disk tuning reads and
  writes. Defaults to `/sys/block`; only meant to be overridden by tests,
  to point at a fake tree instead of the host's real disks.

With `cassandra_linux_tune_data_disk` true, the read-ahead is set on the
disk, and the IO scheduler set to `none` on
SSD/NVMe disks only (`queue/rotational` 0): spinning disks keep theirs. Both
are applied immediately through sysfs, then kept across reboots with a udev
rule (`/etc/udev/rules.d/61-cassandra-data-disk.rules`) matching the disk by
the first stable id udev knows for it (`ID_WWN_WITH_EXTENSION`, `ID_WWN`,
`ID_SERIAL`, `ID_PATH`), or
else by its name. In containers, the disk is not tuned (it is the host's).
The rule is not removed when the tuning is turned off: delete the file.

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
         - { role: cassandra_linux, x: 42 }

License
-------

BSD

Author Information
------------------

An optional section for the role authors to include contact information, or a
website (HTML is not allowed).

References
__________

The following sources of information were used extensively for this role:

* https://docs.datastax.com/en/docker/doc/docker/dockerRecommendedSettings.html
* https://docs.datastax.com/en/cassandra/3.0/cassandra/install/installRecommendSettings.html
* https://docs.datastax.com/en/dse/5.1/dse-admin/datastax_enterprise/config/configRecommendedSettings.html
