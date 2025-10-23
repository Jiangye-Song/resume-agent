# 🔄 Database Migration Plan: `projects` → `records`

## 📋 Executive Summary

This document outlines the migration strategy for transforming the current `projects`-only table into a more flexible `records` table that supports multiple record types (projects, experience, education, etc.), with enhanced metadata concatenation during vector upsert and plans for a future admin panel.

---

## 🎯 Migration Objectives

1. **Rename Table**: `projects` → `records` (generic naming for multi-type support)
2. **Add Type System**: New `type` column to support multiple record types (project, experience, education, etc.)
3. **Rename Columns**: `project_detail_site` → `detail_site` (generic naming)
4. **Add Additional URLs**: New `additional_url TEXT[][]` column for multiple labeled URLs
5. **Remove JSONB Data**: Remove `data` column, use dedicated columns instead
6. **Enhance Metadata Concatenation**: Improve vector upsert to include ALL fields (title, tags, URLs, dates) in embedded text
7. **Prepare for Admin Panel**: Design schema to support future CRUD operations

---

## 📊 Current vs. Target Schema Comparison

### **Current Schema: `projects`**
```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    tags TEXT[],
    project_detail_site TEXT,
    data JSONB,
    start_date DATE,
    end_date DATE,
    priority INTEGER DEFAULT 3
);
```

### **Target Schema: `records`**
```sql
CREATE TABLE records (
    id TEXT PRIMARY KEY,
    type TEXT DEFAULT 'project' NOT NULL,
    title TEXT DEFAULT 'untitled' NOT NULL,
    summary TEXT,
    tags TEXT[],
    detail_site TEXT,
    additional_url TEXT[][],
    start_date DATE,
    end_date DATE,
    priority INTEGER DEFAULT 3 NOT NULL
);
```

### **Key Schema Changes**
| Change | Old | New | Rationale |
|--------|-----|-----|-----------|
| ✅ Table name | `projects` | `records` | Generic naming for multi-type support |
| ✅ Type field | ❌ None | ✅ `type TEXT NOT NULL` | Discriminate record types (project/experience/education) |
| ✅ Title field | ✅ `title TEXT` | ✅ `title TEXT NOT NULL` | **Kept unchanged** - already exists, just add NOT NULL constraint |
| ✅ URL field | `project_detail_site` | `detail_site` | Generic naming (removed "project" prefix) |
| ✅ Additional URLs | ❌ None | ✅ `additional_url TEXT[][]` | Support multiple URLs with labels |
| ✅ Date type | `DATE` | `DATE` | **Kept unchanged** - already proper type |
| ✅ JSONB data | ✅ `data` column | ❌ Removed | Move structured data to dedicated columns |
| ✅ Priority constraint | `DEFAULT 3` | `DEFAULT 3 NOT NULL` | **Kept unchanged** - just add NOT NULL constraint |

---

## 🗂️ Enhanced Record Type System

### **Supported Record Types**

| Type | Description | Example Use Case |
|------|-------------|------------------|
| `project` | Technical projects, portfolio items | Resume AI Assistant, Portfolio Website |
| `experience` | Work experience, internships | Software Engineer at Google (2020-2023) |
| `education` | Academic credentials | B.S. Computer Science, Stanford University |
| `certification` | Professional certifications | AWS Certified Solutions Architect |
| `publication` | Research papers, blog posts | "Scaling RAG Systems" (Medium, 2024) |
| `award` | Achievements, honors | Best Startup Award 2023 |

### **Type-Specific Metadata Examples**

#### **Project Record**
```json
{
  "id": "proj-resume-agent",
  "type": "project",
  "title": "Resume AI Assistant",
  "summary": "RAG-based resume assistant using Upstash Vector & Groq",
  "tags": ["python", "rag", "llm", "vector-db"],
  "detail_site": "https://github.com/user/resume-agent",
  "additional_url": [
    ["demo", "https://resume-agent.vercel.app"],
    ["docs", "https://docs.resume-agent.io"]
  ],
  "start_date": "2024-08",
  "end_date": "ongoing",
  "priority": 3
}
```

#### **Experience Record**
```json
{
  "id": "exp-google-swe",
  "type": "experience",
  "title": "Software Engineer at Google Cloud",
  "summary": "Worked on Kubernetes infrastructure and container orchestration",
  "tags": ["kubernetes", "go", "distributed-systems"],
  "detail_site": "https://linkedin.com/in/user",
  "additional_url": [
    ["company", "https://cloud.google.com"]
  ],
  "start_date": "2020-06",
  "end_date": "2023-03",
  "priority": 2
}
```

#### **Education Record**
```json
{
  "id": "edu-stanford-cs",
  "type": "education",
  "title": "B.S. Computer Science, Stanford University",
  "summary": "Bachelor of Science in Computer Science, GPA 3.9/4.0, Focus on Machine Learning and Algorithms",
  "tags": ["computer-science", "ml", "algorithms"],
  "detail_site": "https://cs.stanford.edu",
  "additional_url": [
    ["transcript", "https://drive.google.com/transcript.pdf"]
  ],
  "start_date": "2016-09",
  "end_date": "2020-06",
  "priority": 2
}
```

---

## 🔧 Implementation Strategy

### **Phase 1: Database Schema Migration** (Week 1)

#### **1.1 Create Migration Script**
File: `db_migrate_to_records.py`

**Tasks:**
- ✅ Create new `records` table with target schema
- ✅ Migrate existing `projects` data → `records` (with `type='project'`)
- ✅ Copy `title` column as-is (already exists in current schema)
- ✅ Rename `project_detail_site` → `detail_site`
- ✅ Add new `type` column (default to 'project' for existing records)
- ✅ Add new `additional_url` column (initialize as NULL or empty array)
- ✅ Remove `data` JSONB column (data already in dedicated columns)
- ✅ Validate data integrity (no NULL primary keys, required fields)
- ✅ Create backup of `projects` table before migration

**Sample Migration Logic:**
```python
# Pseudocode
async def migrate_projects_to_records():
    # 1. Create new records table
    await conn.execute(CREATE_RECORDS_TABLE_SQL)
    
    # 2. Direct data migration with simple column mapping
    # Most columns map 1:1, we just add 'type' and rename 'project_detail_site'
    await conn.execute("""
        INSERT INTO records (
            id, type, title, summary, tags, detail_site, 
            additional_url, start_date, end_date, priority
        )
        SELECT 
            id,
            'project' AS type,           -- NEW: Add type column
            title,                        -- KEEP: Copy as-is
            summary,                      -- KEEP: Copy as-is
            tags,                         -- KEEP: Copy as-is
            project_detail_site,          -- RENAME: to detail_site
            NULL::TEXT[][],               -- NEW: Additional URLs (empty for now)
            start_date,                   -- KEEP: Copy as-is
            end_date,                     -- KEEP: Copy as-is
            priority                      -- KEEP: Copy as-is
        FROM projects
    """)
    
    # 3. Verify migration
    old_count = await conn.fetchval("SELECT COUNT(*) FROM projects")
    new_count = await conn.fetchval("SELECT COUNT(*) FROM records WHERE type='project'")
    assert old_count == new_count, f"Migration count mismatch: {old_count} vs {new_count}"
    
    # 4. Rename old table as backup
    await conn.execute("ALTER TABLE projects RENAME TO projects_backup")
    
    print(f"✅ Migrated {new_count} records from projects to records table")
```

#### **1.2 Update Seed Script**
File: `db_seed_records.py` (replace `db_seed_projects.py`)

**Tasks:**
- ✅ Create seed data for multiple record types (projects, experience, education)
- ✅ Update INSERT logic for new `records` schema
- ✅ Add sample data demonstrating `additional_url` array usage

---

### **Phase 2: Application Code Updates** (Week 1-2)

#### **2.1 Update Migration Utilities**
File: `migrate_utils.py`

**Current Issues:**
- ❌ Hardcoded `projects` table name (need to change to `records`)
- ❌ Hardcoded column name `project_detail_site` (need to change to `detail_site`)
- ❌ Doesn't handle `type` column (need to read and use it)
- ❌ Doesn't handle `additional_url` column (need to include in metadata)
- ❌ Limited metadata concatenation (currently only `title + summary`, need to include tags, URLs, dates)

**Required Changes:**

**A. Query Logic**
```python
# OLD
rows = await conn.fetch('''
    SELECT id, title, summary, tags, project_detail_site, data, start_date, end_date, priority 
    FROM projects 
    ORDER BY priority DESC, id
''')

# NEW
rows = await conn.fetch('''
    SELECT id, type, title, summary, tags, detail_site, additional_url, 
           start_date::text as start_date, end_date::text as end_date, priority 
    FROM records 
    ORDER BY priority DESC, type, id
''')
```

**B. Metadata Building**
```python
# OLD - Basic concatenation
enriched_text = f"{title}. {summary}" if summary else str(title)
metadata = {
    'title': title,
    'summary': summary,
    'tags': item.get('tags', []),
    'project-detail-site': item.get('project-detail-site', ''),
    'priority': item.get('priority', 3),
    'source': 'project'
}

# NEW - Enhanced concatenation with all fields
def build_enriched_text(record):
    """Build comprehensive text for vector embedding with ALL metadata"""
    parts = []
    
    # Title (highest semantic weight)
    if record.get('title'):
        parts.append(record['title'])
    
    # Core summary
    if record.get('summary'):
        parts.append(record['summary'])
    
    # Tags (inline)
    if record.get('tags'):
        tags_str = ', '.join(record['tags'])
        parts.append(f"Technologies: {tags_str}")
    
    # URLs (inline)
    if record.get('detail_site'):
        parts.append(f"Details at: {record['detail_site']}")
    
    if record.get('additional_url'):
        for label, url in record['additional_url']:
            parts.append(f"{label}: {url}")
    
    # Dates (inline)
    if record.get('start_date') or record.get('end_date'):
        date_str = f"Duration: {record.get('start_date', 'N/A')} to {record.get('end_date', 'present')}"
        parts.append(date_str)
    
    # Type indicator
    parts.append(f"Type: {record.get('type', 'project')}")
    
    return ". ".join(parts)

def build_metadata(record):
    """Build metadata dict for vector storage"""
    return {
        'id': record['id'],
        'type': record.get('type', 'project'),
        'title': record.get('title', 'untitled'),
        'summary': record.get('summary', ''),
        'tags': record.get('tags', []),
        'detail_site': record.get('detail_site', ''),
        'additional_url': record.get('additional_url', []),
        'start_date': record.get('start_date'),
        'end_date': record.get('end_date'),
        'priority': record.get('priority', 3),
        'source': record.get('type', 'project')  # Use type as source
    }

# Usage in upsert loop
for record in rows:
    enriched_text = build_enriched_text(record)
    metadata = build_metadata(record)
    rid = f"{record['type']}:{record['id']}"  # Namespace by type
    
    await asyncio.to_thread(index.upsert, [(str(rid), enriched_text, metadata)])
```

**C. Type-Based Filtering** (Optional Enhancement)
```python
# Support filtering by record type during migration
async def migrate_records_async(record_types=None):
    """
    Args:
        record_types: List of types to migrate (e.g., ['project', 'experience'])
                      If None, migrate all types
    """
    query = "SELECT * FROM records ORDER BY priority DESC, type, id"
    if record_types:
        placeholders = ','.join(['$' + str(i+1) for i in range(len(record_types))])
        query = f"SELECT * FROM records WHERE type IN ({placeholders}) ORDER BY priority DESC, type, id"
        rows = await conn.fetch(query, *record_types)
    else:
        rows = await conn.fetch(query)
    # ... rest of migration logic
```

#### **2.2 Update RAG Query Logic**
File: `rag_run.py`

**Required Changes:**

**A. Load Function**
```python
# OLD
async def load_projects_from_db():
    rows = await conn.fetch('SELECT id, title, summary, tags, project_detail_site, data, start_date, end_date, priority FROM projects ...')

# NEW
async def load_records_from_db():
    rows = await conn.fetch('SELECT id, type, title, summary, tags, detail_site, additional_url, start_date, end_date, priority FROM records ...')
    
    items = []
    for r in rows:
        item = {
            'id': r['id'],
            'type': r['type'],
            'title': r['title'],
            'summary': r['summary'],
            'tags': list(r['tags']) if r['tags'] else [],
            'detail_site': r['detail_site'],
            'additional_url': r['additional_url'],
            'start_date': r['start_date'].isoformat() if r['start_date'] else None,
            'end_date': r['end_date'].isoformat() if r['end_date'] else None,
            'priority': r['priority'],
            '_source': r['type']
        }
        items.append(item)
    return items
```

**B. Metadata Display**
```python
# Update console output to show record type
print(f"🔹 Source {i + 1} [{priority_label}] Type: {result['metadata'].get('type', 'project')} (ID: {doc_id}, score={score:.4f}):")
```

**C. Context Building**
```python
# Already handles metadata well via enriched_text
# Just ensure metadata includes all new fields (detail_site, additional_url, etc.)
```

#### **2.3 Update CLI Scripts**
Files: `upsert_projects_to_vector.py`, `db_seed_projects.py`

**Tasks:**
- ✅ Rename `upsert_projects_to_vector.py` → `upsert_records_to_vector.py`
- ✅ Update imports and function calls
- ✅ Add CLI arguments for record type filtering:
  ```powershell
  python upsert_records_to_vector.py --types project,experience
  python upsert_records_to_vector.py --dry-run
  ```

#### **2.4 Update API Endpoints**
Files: `api/upsert-projects.py`, `api/chat.py`

**Tasks:**
- ✅ Rename `api/upsert-projects.py` → `api/upsert-records.py`
- ✅ Update Vercel routing in `vercel.json`:
  ```json
  {
    "rewrites": [
      { "source": "/api/upsert", "destination": "/api/upsert-records.py" },
      { "source": "/api/chat", "destination": "/api/chat.py" }
    ]
  }
  ```
- ✅ Update API documentation in README

---

### **Phase 3: Enhanced Vector Metadata** (Week 2)

#### **3.1 Improve Enriched Text Building**

**Current State:** Basic `title + summary` concatenation (missing tags, URLs, dates, type)

**Target State:** Comprehensive metadata concatenation including ALL fields

**This is the KEY improvement** - The upsert script will now concatenate all metadata fields (title, summary, tags, URLs, dates, type) into the embedded text for better semantic search.

**Implementation:**
```python
def build_enriched_text_v2(record):
    """
    Build rich text embedding that includes ALL searchable information:
    - Title (main identifier - highest semantic weight)
    - Summary (detailed content)
    - Tags (keywords for semantic search)
    - URLs (for reference in results)
    - Dates (temporal context)
    - Type (context for filtering)
    """
    components = []
    
    # 1. Title (highest semantic weight for identification)
    if record.get('title'):
        components.append(record['title'])
    
    # 2. Core summary (detailed content)
    if record.get('summary'):
        components.append(record['summary'])
    
    # 3. Tags (keyword search optimization)
    if record.get('tags'):
        tags_str = ' '.join(record['tags'])  # Space-separated for better embedding
        components.append(f"Keywords: {tags_str}")
    
    # 4. Detail site (for URL-based queries)
    if record.get('detail_site'):
        components.append(f"Website: {record['detail_site']}")
    
    # 5. Additional URLs with labels
    if record.get('additional_url'):
        for label, url in record['additional_url']:
            components.append(f"{label.capitalize()}: {url}")
    
    # 6. Temporal information
    date_parts = []
    if record.get('start_date'):
        date_parts.append(f"from {record['start_date']}")
    if record.get('end_date'):
        date_parts.append(f"to {record['end_date']}")
    if date_parts:
        components.append(f"Duration {' '.join(date_parts)}")
    
    # 7. Type context (helps with "show me your experience" queries)
    record_type = record.get('type', 'project')
    components.append(f"Category: {record_type}")
    
    # Join with periods for natural sentence structure
    return ". ".join(components) + "."
```

**Benefits:**
- 🎯 **Better Semantic Search**: Tags and keywords embedded in text
- 🔗 **URL Discoverability**: Detail sites included in embeddings
- 📅 **Temporal Queries**: "Show me projects from 2024" now works
- 🏷️ **Type Awareness**: "Tell me about your experience" filters correctly

#### **3.2 Metadata Optimization**

**Storage vs. Embedding Trade-off:**
- **Store in metadata**: IDs, priority, structured data (for filtering)
- **Embed in text**: Summary, tags, URLs (for semantic search)

**Recommended Metadata Structure:**
```python
metadata = {
    # Searchable (also in enriched_text)
    'title': record['title'],
    'summary': record['summary'],
    'tags': record['tags'],
    'detail_site': record['detail_site'],
    
    # Filterable (metadata-only)
    'id': record['id'],
    'type': record['type'],
    'priority': record['priority'],
    'start_date': record['start_date'],
    'end_date': record['end_date'],
    
    # Display (for result rendering)
    'additional_url': record['additional_url'],
    
    # Legacy compatibility
    'source': record['type']
}
```

---

### **Phase 4: Admin Panel Design** (Week 3-4)

#### **4.1 Architecture Overview**

**Tech Stack:**
- **Frontend**: React + TailwindCSS (or keep simple HTML/CSS)
- **Backend**: FastAPI endpoints in `api/admin/`
- **Auth**: Vercel Edge Config for simple API key auth
- **Database**: Existing Neon Postgres via `asyncpg`

**Endpoints:**
```plaintext
POST   /api/admin/records         # Create new record
GET    /api/admin/records         # List all records (with pagination)
GET    /api/admin/records/:id     # Get single record
PUT    /api/admin/records/:id     # Update record
DELETE /api/admin/records/:id     # Delete record
POST   /api/admin/upsert          # Trigger vector upsert for specific record(s)
```

#### **4.2 Admin Panel Features**

**Phase 4A: Basic CRUD (Week 3)**
- ✅ List all records with type badges and priority indicators
- ✅ Create new record form with type dropdown
- ✅ Edit existing record (inline or modal)
- ✅ Delete record with confirmation
- ✅ Simple API key auth via `ADMIN_API_KEY` env var

**Phase 4B: Advanced Features (Week 4)**
- ✅ Bulk operations (multi-select + bulk delete/priority update)
- ✅ Search/filter by type, tags, date range
- ✅ Drag-and-drop priority reordering
- ✅ "Sync to Vector" button (calls upsert API for selected records)
- ✅ Preview enriched text before upsert
- ✅ Vector DB sync status indicator (last synced timestamp)

#### **4.3 Sample Admin UI Mockup**

**Records List Page:**
```
╔═══════════════════════════════════════════════════════════════════════╗
║ 📋 Resume Records Admin                      [+ New Record] [🔄 Sync] ║
╠═══════════════════════════════════════════════════════════════════════╣
║ 🔍 Search: [_______]  Type: [All ▼]  Priority: [All ▼]              ║
╠═══════════════════════════════════════════════════════════════════════╣
║ ☐ | Type    | ID              | Summary               | Priority | ⚙️ ║
╠═══════════════════════════════════════════════════════════════════════╣
║ ☐ | Project | proj-resume-ai  | RAG-based resume...   | 🔴 3     | ✏️❌║
║ ☐ | Exp     | exp-google-swe  | Software Engineer at..| 🟠 2     | ✏️❌║
║ ☐ | Edu     | edu-stanford-cs | B.S. Computer Sci...  | 🟡 1     | ✏️❌║
╚═══════════════════════════════════════════════════════════════════════╝
```

**Create/Edit Form:**
```
╔═══════════════════════════════════════════════════════════════╗
║ ✏️ Edit Record: proj-resume-ai                               ║
╠═══════════════════════════════════════════════════════════════╣
║ Type:        [Project ▼]                                     ║
║ ID:          [proj-resume-ai]                                ║
║ Title:       [Resume AI Assistant]                           ║
║ Summary:     [RAG-based resume assistant using Upstash...]   ║
║ Tags:        [python, rag, llm, vector-db]                   ║
║ Detail Site: [https://github.com/user/resume-agent]          ║
║ Start Date:  [2024-08]                                       ║
║ End Date:    [ongoing]                                       ║
║ Priority:    [3 - Highest ▼]                                 ║
║                                                               ║
║ Additional URLs:                                              ║
║   [demo] [https://resume-agent.vercel.app]     [➖]          ║
║   [docs] [https://docs.resume-agent.io]        [➖]          ║
║   [+ Add URL]                                                 ║
║                                                               ║
║                              [Cancel]  [Save & Sync Vector]  ║
╚═══════════════════════════════════════════════════════════════╝
```

#### **4.4 Admin API Implementation**

File: `api/admin/records.py`

**Sample CRUD Endpoint:**
```python
from fastapi import FastAPI, HTTPException, Header
import os
import asyncpg

app = FastAPI()

ADMIN_API_KEY = os.getenv('ADMIN_API_KEY')

def verify_admin(x_api_key: str = Header(None)):
    if not ADMIN_API_KEY or x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail='Unauthorized')

@app.get('/api/admin/records')
async def list_records(
    x_api_key: str = Header(None),
    type: str = None,
    limit: int = 50,
    offset: int = 0
):
    verify_admin(x_api_key)
    
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        query = 'SELECT * FROM records ORDER BY priority DESC, type, id LIMIT $1 OFFSET $2'
        params = [limit, offset]
        
        if type:
            query = 'SELECT * FROM records WHERE type = $1 ORDER BY priority DESC, id LIMIT $2 OFFSET $3'
            params = [type, limit, offset]
        
        rows = await conn.fetch(query, *params)
        return {'records': [dict(r) for r in rows]}
    finally:
        await conn.close()

@app.post('/api/admin/records')
async def create_record(record: dict, x_api_key: str = Header(None)):
    verify_admin(x_api_key)
    
    # Validate required fields
    required = ['id', 'type', 'title']
    if not all(k in record for k in required):
        raise HTTPException(status_code=400, detail='Missing required fields')
    
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        # Convert date strings to date objects if needed
        start_date = record.get('start_date')
        end_date = record.get('end_date')
        
        await conn.execute('''
            INSERT INTO records (id, type, title, summary, tags, detail_site, additional_url, start_date, end_date, priority)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::date, $9::date, $10)
        ''', record['id'], record['type'], record.get('title', 'untitled'), record.get('summary'),
             record.get('tags', []), record.get('detail_site'), record.get('additional_url', []),
             start_date, end_date, record.get('priority', 3))
        
        return {'status': 'created', 'id': record['id']}
    finally:
        await conn.close()

# Similar implementations for PUT, DELETE endpoints...
```

---

## 📝 Migration Checklist

### **Pre-Migration**
- [ ] ✅ Backup current `projects` table to `projects_backup`
- [ ] ✅ Review all records for data quality (no NULL ids, valid tags)
- [ ] ✅ Test migration script on local database
- [ ] ✅ Update `.env` with new environment variables if needed

### **Database Migration**
- [ ] ✅ Run `db_migrate_to_records.py` on production Neon database
- [ ] ✅ Verify row counts match: `SELECT COUNT(*) FROM projects_backup` = `SELECT COUNT(*) FROM records WHERE type='project'`
- [ ] ✅ Spot-check migrated data for accuracy
- [ ] ✅ Create sample records for new types (experience, education)

### **Code Updates**
- [ ] ✅ Update `migrate_utils.py` with new table name and schema
- [ ] ✅ Update `rag_run.py` load functions
- [ ] ✅ Rename and update CLI scripts
- [ ] ✅ Update API endpoints and `vercel.json` routes
- [ ] ✅ Update `requirements.txt` if new dependencies added

### **Testing**
- [ ] ✅ Test local upsert: `python upsert_records_to_vector.py`
- [ ] ✅ Test RAG queries with new schema
- [ ] ✅ Test API endpoints locally (`api/chat.py`, `api/upsert-records.py`)
- [ ] ✅ Deploy to Vercel and test production endpoints
- [ ] ✅ Verify vector DB contains updated metadata

### **Documentation**
- [ ] ✅ Update `README.md` with new table schema
- [ ] ✅ Update API documentation
- [ ] ✅ Document new record types and examples
- [ ] ✅ Add admin panel documentation (once implemented)

### **Post-Migration**
- [ ] ✅ Monitor error logs for migration-related issues
- [ ] ✅ Drop `projects_backup` table after 30 days of stable operation
- [ ] ✅ Optimize vector queries for performance
- [ ] ✅ Implement admin panel (Phase 4)

---

## 🚀 Deployment Strategy

### **Deployment Timeline**

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1: Schema Migration | Week 1 | New `records` table, migrated data |
| Phase 2: Code Updates | Week 1-2 | Updated app code, APIs, CLI tools |
| Phase 3: Enhanced Metadata | Week 2 | Improved vector embeddings |
| Phase 4: Admin Panel | Week 3-4 | Full CRUD admin interface |

### **Rollback Plan**

If migration fails or causes issues:

1. **Immediate Rollback:**
   ```sql
   ALTER TABLE records RENAME TO records_failed;
   ALTER TABLE projects_backup RENAME TO projects;
   ```

2. **Code Rollback:**
   - Revert to previous Git commit
   - Redeploy previous version to Vercel

3. **Vector DB:**
   - Old vectors with `project:*` IDs still exist
   - No need to rollback vector DB if Postgres rolled back

### **Monitoring**

**Key Metrics to Track:**
- ✅ Database query latency (should remain < 100ms)
- ✅ Vector search accuracy (test with known queries)
- ✅ API error rates (should be < 1%)
- ✅ Memory usage (ensure no leaks from new code)

**Alerting:**
- ✅ Set up Vercel alerts for 5xx errors
- ✅ Monitor Neon database connection pool usage
- ✅ Track Upstash Vector query latency

---

## 🎨 Admin Panel UI/UX Considerations

### **Design Principles**
1. **Simplicity First**: Clean, minimal interface (avoid over-engineering)
2. **Mobile Responsive**: Should work on tablets/phones
3. **Keyboard Shortcuts**: Power users can navigate quickly
4. **Inline Editing**: Edit fields directly in table view
5. **Batch Operations**: Multi-select for bulk actions

### **Security**
- ✅ API key authentication (env var `ADMIN_API_KEY`)
- ✅ Rate limiting on admin endpoints (10 req/min per IP)
- ✅ Input sanitization to prevent SQL injection
- ✅ CORS restrictions (only allow admin panel domain)

### **Future Enhancements** (Post-MVP)
- 📊 Analytics dashboard (most viewed records, search trends)
- 🔄 Auto-sync to vector DB on save (webhook to upsert)
- 📤 Export/import records as JSON
- 🎨 Rich text editor for summary field (Markdown support)
- 🔔 Notifications for sync failures

---

## 📚 Technical Debt & Known Issues

### **Current Technical Debt**
1. ❌ No automated tests for migration logic
2. ❌ No database transaction rollback on partial migration failure
3. ❌ Hardcoded table names in multiple files (need constants)
4. ❌ No pagination for large record sets in RAG queries
5. ❌ No caching layer for frequently queried records

### **Post-Migration TODOs**
1. ✅ Add unit tests for `build_enriched_text()` and `build_metadata()`
2. ✅ Implement database connection pooling for performance
3. ✅ Add logging middleware for all API calls
4. ✅ Create constants file for table/column names
5. ✅ Implement Redis caching for system prompt and config

---

## 🤝 Next Steps

### **Immediate Actions (This Week)**
1. ✅ Review and approve this migration plan
2. ✅ Set up local development environment with new schema
3. ✅ Write and test `db_migrate_to_records.py` script
4. ✅ Update `migrate_utils.py` and test locally

### **Next Week**
1. ✅ Deploy database migration to production Neon
2. ✅ Update all application code and redeploy to Vercel
3. ✅ Test production system end-to-end
4. ✅ Begin admin panel development

### **Future Phases**
1. ✅ Complete admin panel CRUD operations
2. ✅ Add bulk operations and advanced filtering
3. ✅ Implement auto-sync on record save
4. ✅ Add analytics and monitoring dashboard

---

## 📞 Questions & Decisions Needed

### ✅ **RESOLVED Decisions:**

1. **Title Column:** ✅ Keep as-is with `NOT NULL` constraint
2. **Date Type:** ✅ Keep as `DATE` type (already correct)
3. **Priority:** ✅ Keep as-is with `NOT NULL` constraint
4. **Table Name:** ✅ Rename `projects` → `records`
5. **Type System:** ✅ Add `type TEXT DEFAULT 'project' NOT NULL`
6. **JSONB Data:** ✅ Remove `data` column (redundant with dedicated columns)

### ⏳ **Pending Decisions:**

1. **Additional URL Array Structure:** Confirm `TEXT[][]` (2D array) is acceptable?
   - Each row: `[label, url]` e.g., `[['demo', 'https://...'], ['docs', 'https://...']]`
   - Alternative: Use JSONB `[{"label": "demo", "url": "https://..."}]`
   - **Current Plan**: Use `TEXT[][]` for simplicity

2. **Admin Panel Auth:** API key vs. full OAuth (Google/GitHub login)?
   - **Current Plan**: Start with API key, add OAuth in Phase 4B if needed

3. **Vector DB Namespace:** Keep `project:*` for backward compatibility or rename to `record:*`?
   - **Current Plan**: Use `{type}:{id}` (e.g., `project:id`, `experience:id`) for better filtering

---

## 📎 Appendix

### **A. SQL Scripts**

#### **Create Records Table**
```sql
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    type TEXT DEFAULT 'project' NOT NULL,
    title TEXT DEFAULT 'untitled' NOT NULL,
    summary TEXT,
    tags TEXT[],
    detail_site TEXT,
    additional_url TEXT[][],
    start_date DATE,
    end_date DATE,
    priority INTEGER DEFAULT 3 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_records_type ON records(type);
CREATE INDEX idx_records_priority ON records(priority DESC);
CREATE INDEX idx_records_tags ON records USING GIN(tags);
CREATE INDEX idx_records_title ON records(title);
```

#### **Migration Script**
```sql
-- Backup existing projects table
CREATE TABLE projects_backup AS SELECT * FROM projects;

-- Insert migrated data into records
INSERT INTO records (id, type, title, summary, tags, detail_site, additional_url, start_date, end_date, priority)
SELECT 
    id,
    'project' AS type,
    COALESCE(title, 'untitled') AS title,  -- Keep original title or default to 'untitled'
    summary,
    tags,
    project_detail_site AS detail_site,
    NULL::TEXT[][] AS additional_url,  -- Populate manually if needed
    start_date,  -- Keep as DATE type
    end_date,    -- Keep as DATE type
    priority
FROM projects;

-- Verify migration
SELECT 
    (SELECT COUNT(*) FROM projects) AS old_count,
    (SELECT COUNT(*) FROM records WHERE type='project') AS new_count,
    (SELECT COUNT(*) FROM projects) = (SELECT COUNT(*) FROM records WHERE type='project') AS counts_match;
```

### **B. Environment Variables**

```env
# Database
DATABASE_URL=postgresql://user:pass@host:port/db
DATABASE_URL_UNPOOLED=postgresql://user:pass@host:port/db

# Vector DB
UPSTASH_VECTOR_REST_URL=https://xxx.upstash.io
UPSTASH_VECTOR_REST_TOKEN=xxx
VECTOR_DB_TYPE=upstash

# LLM
GROQ_API_KEY=xxx
LLM_PROVIDER=groq
GROQ_MODEL=deepseek-r1-distill-llama-70b

# Admin Panel (new)
ADMIN_API_KEY=your-secret-admin-key-here

# Migration (optional)
MIGRATION_KEY=your-migration-key-here
```

### **C. File Rename Mapping**

| Old Filename | New Filename | Status |
|--------------|--------------|--------|
| `db_seed_projects.py` | `db_seed_records.py` | ✅ Rename |
| `upsert_projects_to_vector.py` | `upsert_records_to_vector.py` | ✅ Rename |
| `api/upsert-projects.py` | `api/upsert-records.py` | ✅ Rename |
| `migrate_utils.py` | `migrate_utils.py` | ⚠️ Update only |
| `rag_run.py` | `rag_run.py` | ⚠️ Update only |

---

**Document Version:** 1.0  
**Last Updated:** October 16, 2025  
**Author:** GitHub Copilot  
**Status:** 📋 Pending Review
