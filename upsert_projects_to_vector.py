"""
Read records from Postgres and upsert them into Upstash Vector with enhanced metadata.

Usage:
    python upsert_projects_to_vector.py

It reads DATABASE_URL and UPSTASH_VECTOR_REST_URL/UPSTASH_VECTOR_REST_TOKEN from environment.

The script now:
- Reads from 'records' table (instead of 'projects')
- Supports multiple record types (project, experience, education, etc.)
- Concatenates ALL metadata fields into enriched text:
  * Title, summary, tags, URLs, dates, type
- Creates namespaced vector IDs: {type}:{id}
"""
from migrate_utils import migrate_records


if __name__ == '__main__':
    print("🚀 Starting records migration to Upstash Vector...")
    print("📊 Reading from 'records' table and building enhanced metadata...\n")
    
    stats = migrate_records()
    
    print("\n" + "="*60)
    print("📈 Migration Summary:")
    print("="*60)
    print(f"✅ Total records: {stats['total']}")
    print(f"✅ Successfully upserted: {stats['upserted']}")
    print(f"❌ Errors: {len(stats['errors'])}")
    
    if stats['errors']:
        print("\n⚠️  Error details:")
        for err in stats['errors']:
            print(f"  - Record {err.get('id')} ({err.get('type')}): {err.get('error')}")
    
    print("="*60)
