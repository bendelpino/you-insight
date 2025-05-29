#!/usr/bin/env python3
"""
Script to create PostgreSQL tables for YouInsight app.
This script defines the proper schema with PostgreSQL-specific data types
including JSONB for YouTube API responses and Gemini AI outputs.

Usage:
    python create_postgres_tables.py
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv(verbose=True)

# Hard-code the PostgreSQL connection details from your .env file
# This is just for testing - you'd normally use environment variables
PG_HOST = "aws-0-us-east-2.pooler.supabase.com"
PG_PORT = "6543"
PG_USER = "postgres.skascdzgesuejgsamiaw"
PG_PASSWORD = "Vlz6pQcj2IlpJcDH"
PG_DATABASE = "postgres"

# Direct connection string
DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

# Print connection details for debugging (without password)
print(f"Attempting to connect with:")
print(f"Host: {PG_HOST}")
print(f"Port: {PG_PORT}")
print(f"User: {PG_USER}")
print(f"Database: {PG_DATABASE}")
print(f"Using connection string (password hidden): postgresql://{PG_USER}:***@{PG_HOST}:{PG_PORT}/{PG_DATABASE}")

def connect_postgres():
    """Connect to PostgreSQL database."""
    try:
        # Use the direct connection string
        print(f"Attempting connection to Supabase...")
        conn = psycopg2.connect(DATABASE_URL)
        print(f"Successfully connected to PostgreSQL database on Supabase!")
        return conn
    except psycopg2.Error as e:
        print(f"PostgreSQL connection error: {e}")
        # Print more detailed error information
        print("\nDetailed error information:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error args: {e.args}")
        if hasattr(e, 'diag'):
            print(f"  Message: {e.diag.message_primary}")
            if hasattr(e.diag, 'message_detail'):
                print(f"  Detail: {e.diag.message_detail}")
        return None

def create_tables(conn):
    """Create tables in PostgreSQL database."""
    cursor = conn.cursor()
    
    # List of SQL statements to create tables
    table_statements = [
        # User table
        """
        CREATE TABLE IF NOT EXISTS "user" (
            id SERIAL PRIMARY KEY,
            email VARCHAR(120) UNIQUE NOT NULL,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            gemini_api_key VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reset_token VARCHAR(100),
            reset_token_expiry TIMESTAMP
        );
        """,
        
        # Video table with JSONB for API response
        """
        CREATE TABLE IF NOT EXISTS video (
            id SERIAL PRIMARY KEY,
            video_id VARCHAR(20) NOT NULL,
            title VARCHAR(200) NOT NULL,
            url VARCHAR(200) NOT NULL,
            view_count INTEGER,
            transcript TEXT,
            api_response JSONB,  -- Store complete YouTube API response
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Analysis table with JSONB for Gemini output
        """
        CREATE TABLE IF NOT EXISTS analysis (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES "user"(id) NOT NULL,
            search_term VARCHAR(100),
            prompt TEXT NOT NULL,
            result TEXT,  -- Keep for backward compatibility
            result_json JSONB,  -- Structured Gemini API results
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            conversation_id VARCHAR(100),
            is_conversation BOOLEAN DEFAULT FALSE,
            messages JSONB  -- Conversation messages as JSONB
        );
        """,
        
        # AnalysisVideo joining table
        """
        CREATE TABLE IF NOT EXISTS analysis_video (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER REFERENCES analysis(id) NOT NULL,
            video_id INTEGER REFERENCES video(id) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]
    
    # Create tables
    for statement in table_statements:
        try:
            cursor.execute(statement)
            print(f"Executed SQL: {statement.strip().split()[0:5]}...")
        except psycopg2.Error as e:
            print(f"Error creating table: {e}")
            conn.rollback()
            return False
    
    # Create indexes for better performance
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_video_video_id ON video(video_id);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_user_id ON analysis(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_video_analysis_id ON analysis_video(analysis_id);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_video_video_id ON analysis_video(video_id);",
        # Add JSONB indexes for better performance on JSON fields
        "CREATE INDEX IF NOT EXISTS idx_video_api_response ON video USING GIN (api_response);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_result_json ON analysis USING GIN (result_json);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_messages ON analysis USING GIN (messages);"
    ]
    
    for index in index_statements:
        try:
            cursor.execute(index)
            print(f"Created index: {index}")
        except psycopg2.Error as e:
            print(f"Error creating index: {e}")
            # Continue even if index creation fails
    
    # Commit changes
    conn.commit()
    print("All tables and indexes created successfully!")
    return True

def main():
    """Main function to create tables."""
    # Connect to PostgreSQL
    conn = connect_postgres()
    if not conn:
        print("Failed to connect to PostgreSQL. Exiting.")
        sys.exit(1)
    
    try:
        # Create tables
        if create_tables(conn):
            print("Database setup completed successfully!")
        else:
            print("Database setup failed.")
            sys.exit(1)
    
    finally:
        # Close connection
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
