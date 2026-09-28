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

* `cassandra_linux_apply_live`: apply the kernel settings (sysctl, swapoff,
  THP) live, not only persist them. Defaults to `auto`: live everywhere
  except in containers (Ansible's virtualization facts, and
  `cassandra_linux_container_types`), where `/proc/sys` and `/sys` belong to
  the host; the THP unit is not enabled at boot there either. Set `true` to
  tune the host from a dedicated privileged container, `false` to only
  persist (in containers, only the files). Ansible doesn't detect every
  container (e.g. Kubernetes pods on cgroup v2): set `false` there, the THP
  unit is then still enabled at boot.
* `cassandra_linux_container_types`: `virtualization_type` values taken as
  containers, besides Ansible's own container detection. Defaults to
  `docker`, `podman`, `container`, `containerd`, `lxc`.

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
