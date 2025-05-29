#!/usr/bin/env python3
"""
Script to migrate data from SQLite to PostgreSQL for YouInsight app.
This script will:
1. Extract data from existing SQLite database
2. Transform to PostgreSQL compatible format
3. Load into PostgreSQL database

Usage:
    python migrate_to_postgres.py

Requirements:
    - psycopg2-binary
    - pandas
    - sqlalchemy
    - dotenv
"""

import os
import json
import pandas as pd
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
load_dotenv()

# SQLite database file path
SQLITE_DB_PATH = 'youinsight.db'

# PostgreSQL connection details
PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'postgres')
PG_DATABASE = os.getenv('PG_DATABASE', 'youinsight')

# Connection strings
SQLITE_URI = f'sqlite:///{SQLITE_DB_PATH}'
PG_URI = f'postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}'

def connect_sqlite():
    """Connect to SQLite database."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        print(f"Connected to SQLite database: {SQLITE_DB_PATH}")
        return conn
    except sqlite3.Error as e:
        print(f"SQLite connection error: {e}")
        return None

def connect_postgres():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DATABASE
        )
        print(f"Connected to PostgreSQL database: {PG_DATABASE} on {PG_HOST}")
        return conn
    except psycopg2.Error as e:
        print(f"PostgreSQL connection error: {e}")
        return None

def get_tables(sqlite_conn):
    """Get list of tables from SQLite database."""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    return [table[0] for table in tables if table[0] != 'sqlite_sequence']

def migrate_table(table_name, sqlite_conn, pg_conn):
    """Migrate a single table from SQLite to PostgreSQL."""
    print(f"Migrating table: {table_name}")
    
    # Get data from SQLite
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", sqlite_conn)
    
    if df.empty:
        print(f"No data in table {table_name}. Skipping.")
        return
    
    # Special handling for JSON fields in Analysis and Video tables
    if table_name == 'analysis':
        # Convert messages field from text to JSONB
        if 'messages' in df.columns:
            df['messages'] = df['messages'].apply(
                lambda x: json.loads(x) if pd.notnull(x) and x else None
            )
            # Create result_json from result if it's valid JSON
            df['result_json'] = df['result'].apply(
                lambda x: json.loads(x) if pd.notnull(x) and x and is_valid_json(x) else None
            )
    
    if table_name == 'video':
        # Create api_response column as NULL (will be populated with new data)
        df['api_response'] = None
    
    # Create PostgreSQL cursor
    pg_cursor = pg_conn.cursor()
    
    # Truncate target table to avoid conflicts
    pg_cursor.execute(f"TRUNCATE {table_name} CASCADE;")
    
    # Get column names and prepare SQL
    columns = df.columns.tolist()
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s"
    
    # Convert DataFrame to list of tuples
    values = [tuple(row) for row in df.values]
    
    # Execute insert with execute_values for better performance
    execute_values(pg_cursor, insert_sql, values)
    
    # Reset sequence if the table has an auto-incrementing primary key
    pg_cursor.execute(f"""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = '{table_name}' 
    AND column_default LIKE 'nextval%';
    """)
    seq_columns = pg_cursor.fetchall()
    
    if seq_columns:
        for seq_col in seq_columns:
            pg_cursor.execute(f"""
            SELECT setval(pg_get_serial_sequence('{table_name}', '{seq_col[0]}'), 
                          (SELECT MAX({seq_col[0]}) FROM {table_name}));
            """)
    
    # Commit changes
    pg_conn.commit()
    
    print(f"Successfully migrated {len(df)} rows from {table_name}")

def is_valid_json(text):
    """Check if a string is valid JSON."""
    if not text:
        return False
    try:
        json.loads(text)
        return True
    except:
        return False

def main():
    """Main migration function."""
    # Connect to databases
    sqlite_conn = connect_sqlite()
    pg_conn = connect_postgres()
    
    if not sqlite_conn or not pg_conn:
        print("Failed to connect to one or both databases. Exiting.")
        return
    
    try:
        # Get tables
        tables = get_tables(sqlite_conn)
        
        # The order matters for foreign key constraints
        # Typically migrate tables without foreign keys first
        sorted_tables = sorted(tables, key=lambda x: x != 'user')
        
        for table in sorted_tables:
            migrate_table(table, sqlite_conn, pg_conn)
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
    
    finally:
        # Close connections
        if sqlite_conn:
            sqlite_conn.close()
        if pg_conn:
            pg_conn.close()

if __name__ == "__main__":
    main()
