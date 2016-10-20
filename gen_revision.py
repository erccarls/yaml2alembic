import sys
import os
from subprocess import Popen, PIPE
from string import Template
import yaml

def gen_revision(revision_message):
    '''Given a revision message, generate a new revision and return the filepath
       of the alembic script.

    Parameters
    ----------
    revision_message : str
        Alembic revision message.

    Returns
    -------
    str
        filepath to revision script.
    '''
    # Generate a new revision and capture the output filename.
    p = Popen(["alembic", "revision", "-m", revision_message],
            stdout=PIPE, stderr=PIPE)

    # Read the output and parse the filename of the updated revision.
    for line in p.stdout.readlines():
        print(line)
        
        if 'Generating' in str(line): 
            # Parse out the filename from the stdout returned
            revision_filepath = str(line[13:]).split('...')[0][2:-1]
            print(revision_filepath)

    # Print stderr otherwise. 
    for line in p.stderr.readlines():
        print(line)
    return revision_filepath


def find_line_num(fname, phrase):
    '''
    return the line number of the first instance of phrase. Else return None.
    '''
    with open(fname, 'r') as f:
        for num, line in enumerate(f.readlines()):
            if phrase in line: 
                return num
    return None


def add_imports(revision_filepath, revision_dict):
    '''
    Adds import block at the top of the output revision script.

    Parameters
    ----------
    revision_filepath : str
        Alembic parent directory (which contains alembic.ini).
    revision_dict : dict
        The dictionary result from loading the yaml file of interest.

    Returns
    -------
    None
    '''

    #-----------------------------------
    # Define templates.....
    imports_template = '''$imports\n'''
    # Search for the current last imports line...
    line_num = find_line_num(revision_filepath,
                            phrase='from alembic_addons.table_classes import *')
    # Read the current contents.
    with open(revision_filepath, 'r') as f:
        contents = f.readlines()

    # Insert the new lines 
    contents.insert(line_num+1, 
        Template(imports_template).substitute(imports=revision_dict['imports']))

    # Write out the new file. 
    with open(revision_filepath, 'w') as f:
        contents = f.writelines(contents)


def add_tables(revision_filepath, revision_dict):
    '''
    Specifies and creates tables with columns in the alembic revision script as 
    well as adding to the downgrades.  The strings are generated and then 
    inserted into the alembic script.  We also generate constraints on columns 
    in addition to primary keys. 
    
    Parameters
    ----------
    revision_filepath : str
        Alembic parent directory (which contains alembic.ini). 
    revision_dict : dict
        The dictionary result from loading the yaml file of interest.   

    Returns
    -------
    None
    '''

    table_template = '''
    $table_name = CommentedTable(table_name='$table_name',
                                   schema='$schema',
                                   comment=$table_comment                    )\n'''

    column_template = '''
    $column_name = CommentedColumn(column_name='$column_name',
                                    column_type=$column_data_type,
                                     comment=$column_comment                    ) '''
    add_column_template = '''\n    $table_name.add_column('$column_name')\n'''
    create_table_template = '''    $table_name.create_table()\n'''
    drop_table_template = \
        '''    op.drop_table(table_name="$table_name", schema="$schema")\n'''

    # Create primary key relation template
    pk_template = '''
    op.create_primary_key(constraint_name="$constraint_name",
                          table_name="$table_name",
                          columns=$columns,
                          schema="$schema")\n'''
    
    constraint_template = '''    
    op.create_check_constraint(
        constraint_name="$constraint_name",
        table_name="$table_name",
        condition="$condition",
        schema="$schema")\n'''



    upgrade_body = '' # This will be inserted into the upgrade method body.
    downgrade_body = '' # This will be inserted into the downgrade method body.
    #-----------------------------------
    # Generate templates for each table and for each comment.
    for table_name, table in revision_dict['tables'].items():
        # Table block comment
        upgrade_body += """\n    #-------------""" + table_name \
                      + """-------------#\n"""

        if 'script_comment' in table.keys():
            upgrade_body += '    ' + table['script_comment']

        # Instantiate the table object
        upgrade_body += \
            Template(table_template).substitute(
                table_name=table_name,
                schema=table['schema'],
                table_comment=table['comment'])
        downgrade_body += \
            Template(drop_table_template).substitute(
                table_name=table_name,
                schema=table['schema'])

        # loop over columnss
        for column_name, column in table['columns'].items():
            # Create the columns
            upgrade_body += \
                Template(column_template).substitute(
                    column_name=column_name,
                    column_data_type=column['dtype'],
                    column_comment=column['comment'])
            # Add the columns
            upgrade_body += Template(add_column_template
                                    ).substitute(table_name=table_name,
                                                 column_name=column_name)

        # Create the table
        upgrade_body += Template(create_table_template
                                ).substitute(table_name=table_name)



        #------------------------------------------------
        # Add the primary keys for each table...
        if 'primary_key' not in table.keys():
            print('Warning... No primary key specified for table '+ table_name)
            continue

        # Table block comment
        upgrade_body += """\n    #-------------""" + table_name \
                        + """_pk-------------#\n"""
        # Add the PK revision code. 
        upgrade_body += \
            Template(pk_template).substitute(
                constraint_name=table_name+'_pk',
                table_name=table_name,
                columns=table['primary_key']['columns'],
                schema=table['schema'])


        #------------------------------------------------
        # Add the constraints for the table. 
        if 'constraints' in table.keys():
            for constraint_name, constraint in table['constraints'].items(): 
                # Table block comment
                upgrade_body += """\n    #-------------""" + constraint_name \
                                + """_pk-------------#\n"""
                # Add the PK revision code. 
                upgrade_body += \
                    Template(constraint_template).substitute(
                        constraint_name=table_name+'_'+constraint_name,
                        table_name=table_name,
                        condition=constraint['condition'],
                        schema=table['schema'])


    #----------------------------------
    # Write upgrades to revision file
    line_num = find_line_num(revision_filepath, phrase='def upgrade():')
    # Read the current contents.
    with open(revision_filepath, 'r') as f:
        contents = f.readlines()
    # Insert the new lines
    contents.insert(line_num+1, upgrade_body)
    # Write out the new file.
    with open(revision_filepath, 'w') as f:
        contents = f.writelines(contents)

    #----------------------------------
    # Write downgrades to revision file
    line_num = find_line_num(revision_filepath, phrase='def downgrade():')
    # Read the current contents.
    with open(revision_filepath, 'r') as f:
        contents = f.readlines()
    # Insert the new lines
    contents.insert(line_num+1, downgrade_body)
    # Write out the new file.
    with open(revision_filepath, 'w') as f:
        contents = f.writelines(contents)

    #-----------------------------------
    # Test above.  If works, then insert the string into the location of the
    # upgrade code. Add downgrades too.
    #print(upgrade_body)

def add_foreign_keys(revision_filepath, revision_dict):
    '''
    Generates foreign key relationships for the alembic revision script upgrades 
    and downgrades.  The strings are generated and then inserted into the 
    alembic script.  

    NOTE: Currently foreign keys MUST be added AFTER tables have already been 
    created, and in a separate revision.  It is not presently possible to 
    generate tables at the same time as adding foreign keys. 
    
    Parameters
    ----------
    revision_filepath : str
        Alembic parent directory (which contains alembic.ini). 
    revision_dict : dict
        The dictionary result from loading the yaml file of interest.   

    Returns
    -------
    None
    '''

    fk_template_upgrade = '''
    # Add foreign key constraint to the assignment table
    op.create_foreign_key(
        constraint_name="$constraint_name",
        source_table="$source_table",
        referent_table="$referent_table",
        local_cols=$local_cols,
        remote_cols=$remote_cols,
        source_schema="$source_schema",
        referent_schema="$referent_schema")\n'''

    fk_template_downgrade = '''
    op.drop_constraint(
            constraint_name="$constraint_name",
            table_name="$table_name",
            schema="$schema")\n'''

    upgrade_body = '' # This will be inserted into the upgrade method body.
    downgrade_body = '' # This will be inserted into the downgrade method body.

    #-----------------------------------
    # Generate templates for each foreign key
    for fk_name, fk in revision_dict['foreign_keys'].items():

        # Some quick error checking to ensure we have all the info in the yaml
        for field in ['source_table', 'referent_table',
                      'local_cols', 'remote_cols',
                      'source_schema', 'referent_schema']:
            if field not in fk.keys():
                raise Exception("Foreign key constraint not fully defined!"
                                +"See key definition for " + fk_name)

        # Table block comment
        upgrade_body += ("""\n    #-------------""" + fk['constraint_name']
                         + """-------------#\n""")


        constraint_name = \
            '_'.join([fk['source_table'],
                      fk['referent_table'],   
                      fk['local_cols'].replace('[', '').replace(','"_"),
                      fk['remote_cols'].replace('[', '').replace(','"_")])+'_fk'

        upgrade_body += \
            Template(fk_template_upgrade).substitute(
                constraint_name=constraint_name,
                source_table=fk['source_table'],
                referent_table=fk['referent_table'],
                local_cols=fk['local_cols'],
                remote_cols=fk['remote_cols'],
                source_schema=fk['source_schema'],
                referent_schema=fk['source_schema'])

        downgrade_body += \
            Template(fk_template_downgrade).substitute(
                constraint_name=constraint_name,
                table_name=fk['source_table'],
                schema=fk['source_schema'])

        #----------------------------------
        # Write upgrades to revision file
        line_num = find_line_num(revision_filepath, phrase='def upgrade():')
        # Read the current contents.
        with open(revision_filepath, 'r') as f:
            contents = f.readlines()
        # Insert the new lines
        contents.insert(line_num+1, upgrade_body)
        # Write out the new file.
        with open(revision_filepath, 'w') as f:
            contents = f.writelines(contents)

        #----------------------------------
        # Write downgrades to revision file
        line_num = find_line_num(revision_filepath, phrase='def downgrade():')
        # Read the current contents.
        with open(revision_filepath, 'r') as f:
            contents = f.readlines()
        # Insert the new lines
        contents.insert(line_num+1, downgrade_body)
        # Write out the new file.
        with open(revision_filepath, 'w') as f:
            contents = f.writelines(contents)


if __name__ == "__main__":

    #--------------------------------------------
    # Generate the revision script with alembic
    #--------------------------------------------
    # Check num args...
    if len(sys.argv) != 3:
        raise Exception('''Not enough arguments.  syntax is
                python gen_revision.py <alembic_path> <script_file>''')
    # Load the revision message.
    revision = yaml.load(open(sys.argv[2], 'r'))
    # Change t=o the alembic directory
    os.chdir(sys.argv[1])
    # Generate the revision by calling alembic.
    revision_filepath = gen_revision(revision['revision_message'])

    #--------------------------------------------
    # Edit the script by reading the yaml file in
    # and inserting the necessary operations.
    #--------------------------------------------
    add_imports(revision_filepath, revision)
    add_tables(revision_filepath, revision)





# ------------------------------------
# Now edit the script 


