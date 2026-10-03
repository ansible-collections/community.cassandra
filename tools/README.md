Maintainer tools
================

gen_templates.py
----------------

Generates the `cassandra_config` templates from the stock configuration files
of a Cassandra release. Each template renders back to the stock file with the
role defaults; the molecule scenario checks that line for line.

To move a series to a newer release (e.g. 5.0.9 to 5.0.10), or to add a series:

1. Download and unpack the release tarballs from https://archive.apache.org/dist/cassandra/.
2. Generate the templates. 5.0 is the reference; other series are derived from
   it and need the 5.0 stock `cassandra.yaml`:

       python3 tools/gen_templates.py 5.0 ~/cassandra-5.0.10/conf roles/cassandra_config/templates/5.0
       python3 tools/gen_templates.py 4.1 ~/cassandra-4.1.12/conf roles/cassandra_config/templates/4.1 ~/cassandra-5.0.10/conf/cassandra.yaml

   It fails when a line it replaces is missing or no longer unique (the stock
   file changed there: update the rule), and prints the defaults to add for
   keys the reference does not have.
3. Add the printed defaults to `roles/cassandra_config/defaults/main.yml` and
   `meta/argument_specs.yml` (the unit test `tests/unit/roles` checks they
   match).
4. Copy the stock files to `roles/cassandra_config/molecule/default/files/stock-<release>/`
   (`<name>.stock`), point the tests at them, and update the release in
   `_cassandra_config_template_versions` (`roles/cassandra_config/vars/main.yml`):
   the role tells users when their Cassandra is newer than it.
5. A new series also needs its file list in `_cassandra_config_files`
   (`vars/main.yml`), its Java versions (`cassandra_install`) and its
   repository name (`cassandra_repository`).
6. Run the `cassandra_config` molecule scenario.
