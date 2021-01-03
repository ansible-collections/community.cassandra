# Cassandra Collection
![CI](https://github.com/ansible-collections/community.cassandra/workflows/CI/badge.svg)
![documentation](https://github.com/ansible-collections/community.cassandra/workflows/documentation/badge.svg)
[![Codecov](https://img.shields.io/codecov/c/github/ansible-collections/community.cassandra)](https://codecov.io/gh/ansible-collections/community.cassandra)
![Build & Publish Collection](https://github.com/ansible-collections/community.cassandra/workflows/Build%20&%20Publish%20Collection/badge.svg)

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
