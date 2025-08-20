"""
Read projects from Postgres and upsert them into Upstash Vector with metadata.

Usage:
    python upsert_projects_to_vector.py

It reads DATABASE_URL and UPSTASH_VECTOR_REST_URL/UPSTASH_VECTOR_REST_TOKEN from environment.
"""
from migrate_utils import migrate_projects


if __name__ == '__main__':
    stats = migrate_projects()
    print('Migration stats:', stats)
