# yaml2alembic

This script takes an alembic root directory and a yaml specification (see sample_table.yaml) and generates an alembic revision script. 


TODO: 
Support foreign key constraints 
Support primary key constraints
Support constraints

syntax: 
python gen_revision \<absolute_path_to_alembic_project_dir\> \<absolute_path_to_yaml_spec\>
