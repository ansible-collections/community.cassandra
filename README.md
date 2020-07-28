# Cassandra Collection
![CI](https://github.com/ansible-collections/community.cassandra/workflows/CI/badge.svg?kill_cache=1&test=2)
![documentation](https://github.com/ansible-collections/community.cassandra/workflows/documentation/badge.svg)
[![Codecov](https://img.shields.io/codecov/c/github/ansible-collections/community.cassandra)](https://codecov.io/gh/ansible-collections/community.cassandra)
[![Build Status](https://travis-ci.com/ansible-collections/community.cassandra.svg?branch=master)](https://travis-ci.com/ansible-collections/community.cassandra)
[![Travis Roles](https://travis-ci.com/rhysmeister/AutomatingCassandraWithAnsible.svg?token=EZq8qB3ASZpTwAxAkbiU&branch=master)](https://travis-ci.com/rhysmeister/AutomatingCassandraWithAnsible)
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-1-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

This collection called `cassandra` aims at providing all Ansible modules allowing to interact with Apache Cassandra.

As this is an independent Collection, it can be released on it's own release cadance.

## GitHub workflow

* Maintainers would be members of this GitHub Repo.
* Branch protections could be used to enforce 1 (or 2) reviews from relevant maintainers [CODEOWNERS](.github/CODEOWNERS)

## Contributing

Any contribution is welcome and we only ask contributors to:
* Provide *at least* integration tests for any contribution.
* Create an issues for any significant contribution that would change a large portion of the code base.

## Running integration tests locally

Run all tests

```
ansible-test integration --docker -v --color --retry-on-error --python 3.6 --continue-on-error --diff --coverage
```

Run tests just for the cassandra_role module

```
ansible-test integration --docker -v --color --retry-on-error --python 3.6 --continue-on-error —diff --coverage cassandra_role
```


## License

GNU General Public License v3.0 or later

See LICENCING to see the full text.
