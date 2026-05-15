# Project 8: Natural Language Database Queries

## Overview

Project 8 adds the capability to connect to external databases and query them using natural language. Users can ask questions about their data in plain English, which are automatically converted to SQL queries and executed against their connected databases.

## Features

### 1. **Database Connection Management**

- Connect to multiple databases (PostgreSQL, MySQL, SQLite)
- Store connection credentials securely
- Automatic schema extraction and caching
- Connection health checks
- Activate/deactivate connections without deletion

### 2. **Natural Language to SQL Conversion**

- Uses LLM (Claude/Gemini via LiteLLM) to convert natural language to SQL
- Database-specific SQL generation
- Query validation and safety checks
- Prevents destructive queries (only SELECT allowed)

### 3. **Query Execution & Results**

- Execute generated SQL queries
- Return results as JSON
- Track query execution time
- Store query history for audit trail
- Error handling and reporting

### 4. **Query History & Analytics**

- Store all queries and results
- Query audit trail with timestamps
- Performance metrics (execution time)
- Error tracking

## Architecture

### Database Models

#### `DatabaseConnection`

Stores user database connection details:

```python
- id: UUID (primary key)
- user_id: UUID (foreign key to User)
- name: str (connection name/label)
- db_type: str (postgresql, mysql, sqlite)
- host: str
- port: int
- database_name: str
- username: str
- password: str (encrypted in production)
- ssl_enabled: bool
- is_active: bool
- schema_info: str (JSON with table/column metadata)
- created_at: datetime
- updated_at: datetime
```

#### `DatabaseQuery`

Stores executed queries and results:

```python
- id: UUID (primary key)
- connection_id: UUID (foreign key)
- natural_language_query: str (user's question)
- generated_sql: str (AI-generated SQL)
- result: str (JSON with query results)
- error: str (error message if query failed)
- execution_time_ms: int
- created_at: datetime
```

### Services

#### `DatabaseQueryService`

Core service handling:

- **SQL Generation**: Convert natural language to SQL using LLM
- **Query Execution**: Execute SQL and return results
- **Connection Testing**: Validate database connections
- **Schema Extraction**: Extract database schema information

Key Methods:

```python
async generate_sql_from_natural_language(
    natural_language_query: str,
    schema_info: str,
    db_type: str
) -> str

async execute_query(
    engine: Engine,
    sql_query: str,
    max_rows: int = 1000
) -> tuple[list[dict], float]

async test_connection(connection_string: str) -> bool

async get_schema_info(engine: Engine, db_type: str) -> str

@staticmethod
validate_connection_string(
    db_type: str, host: str, port: int,
    username: str, password: str, database_name: str
) -> str
```

## API Endpoints

### Database Connections

#### Create Connection

```
POST /api/database/connections
```

**Request:**

```json
{
  "name": "Production DB",
  "db_type": "postgresql",
  "host": "db.example.com",
  "port": 5432,
  "database_name": "production",
  "username": "dbuser",
  "password": "secure_password",
  "ssl_enabled": true
}
```

**Response (201):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Production DB",
  "db_type": "postgresql",
  "host": "db.example.com",
  "port": 5432,
  "database_name": "production",
  "username": "dbuser",
  "ssl_enabled": true,
  "is_active": true,
  "schema_info": "Table: users\n  - id: INTEGER (NOT NULL)\n  - email: VARCHAR (NOT NULL)\n  - created_at: TIMESTAMP",
  "created_at": "2026-05-15T10:00:00Z",
  "updated_at": "2026-05-15T10:00:00Z"
}
```

#### List Connections

```
GET /api/database/connections
```

**Response:**

```json
{
  "connections": [
    {
      /* connection objects */
    }
  ]
}
```

#### Get Specific Connection

```
GET /api/database/connections/{connection_id}
```

#### Update Connection

```
PUT /api/database/connections/{connection_id}
```

**Request:**

```json
{
  "name": "Updated Name",
  "password": "new_password",
  "is_active": true
}
```

#### Delete Connection

```
DELETE /api/database/connections/{connection_id}
```

#### Test Connection

```
POST /api/database/connections/{connection_id}/test
```

**Response:**

```json
{
  "status": "success",
  "message": "Connection test passed"
}
```

### Database Queries

#### Execute Natural Language Query

```
POST /api/database/query
```

**Request:**

```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "natural_language_query": "Show me all users who registered in the last 30 days"
}
```

**Response:**

```json
{
  "query_id": "660e8400-e29b-41d4-a716-446655440001",
  "generated_sql": "SELECT * FROM users WHERE created_at >= NOW() - INTERVAL '30 days' LIMIT 1000",
  "result": [
    {
      "id": 1,
      "email": "user1@example.com",
      "created_at": "2026-04-20T15:30:00Z"
    },
    {
      "id": 2,
      "email": "user2@example.com",
      "created_at": "2026-05-01T10:00:00Z"
    }
  ],
  "execution_time_ms": 45
}
```

#### Get Query History

```
GET /api/database/queries/{connection_id}?limit=50
```

**Response:**

```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "connection_id": "550e8400-e29b-41d4-a716-446655440000",
    "natural_language_query": "Show me all users",
    "generated_sql": "SELECT * FROM users LIMIT 1000",
    "result": "[{...}]",
    "error": null,
    "execution_time_ms": 45,
    "created_at": "2026-05-15T10:00:00Z"
  }
]
```

#### Get Query Details

```
GET /api/database/queries/detail/{query_id}
```

## Usage Examples

### Example 1: Connect to Production Database

```bash
curl -X POST http://localhost:8000/api/database/connections \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main DB",
    "db_type": "postgresql",
    "host": "prod-db.example.com",
    "port": 5432,
    "database_name": "ecommerce",
    "username": "app_user",
    "password": "secure_password",
    "ssl_enabled": true
  }'
```

### Example 2: Query with Natural Language

```bash
curl -X POST http://localhost:8000/api/database/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "550e8400-e29b-41d4-a716-446655440000",
    "natural_language_query": "Get the top 10 customers by total spending in 2026"
  }'
```

### Example 3: View Query History

```bash
curl -X GET "http://localhost:8000/api/database/queries/550e8400-e29b-41d4-a716-446655440000?limit=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Security Considerations

### Current Implementation

- ✅ User authentication required for all endpoints
- ✅ Connection isolation (users can only access their own connections)
- ✅ Query isolation (only SELECT queries allowed)
- ✅ Connection pool limits (1000 rows max per query)

### Production Recommendations

1. **Encrypt Passwords**: Store database passwords encrypted in the database

   ```python
   from cryptography.fernet import Fernet

   # Implement encryption for password storage
   cipher = Fernet(encryption_key)
   encrypted_password = cipher.encrypt(password.encode())
   ```

2. **Use Environment Variables**: Don't expose database credentials

   ```python
   # Store sensitive credentials in .env
   DB_PASSWORD_ENCRYPTION_KEY=...
   ```

3. **Rate Limiting**: Add rate limits on query execution

   ```python
   @limiter.limit("10/minute")
   async def execute_natural_language_query(...)
   ```

4. **Query Validation**: Enhance SQL validation
   - Prevent DDL/DML statements
   - Implement query timeout limits
   - Add SQL injection prevention

5. **Audit Logging**: Store comprehensive audit logs
   - Who executed what query
   - Query results
   - Errors and failures

6. **Connection Limits**: Limit concurrent connections per user
   - Max connections per user
   - Connection timeout handling

## Database Setup

### PostgreSQL Support

```bash
# Install driver
pip install asyncpg

# Connection string format
postgresql+asyncpg://user:password@host:port/database
```

### MySQL Support

```bash
# Install driver
pip install asyncmy

# Connection string format
mysql+asyncmy://user:password@host:port/database
```

### SQLite Support

```bash
# Install driver
pip install aiosqlite

# Connection string format
sqlite+aiosqlite:///path/to/database.db
```

## Configuration

Add to `.env`:

```env
# Database Query Feature
MAX_QUERY_RESULTS=1000
QUERY_TIMEOUT_SECONDS=30
MAX_CONCURRENT_QUERIES_PER_USER=5
```

Update `config.py`:

```python
@dataclass(frozen=True)
class Settings:
    # ... existing settings ...

    # Database Query Settings
    max_query_results: int = int(os.getenv("MAX_QUERY_RESULTS", "1000"))
    query_timeout_seconds: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    max_concurrent_queries: int = int(os.getenv("MAX_CONCURRENT_QUERIES_PER_USER", "5"))
```

## Testing

Run database query tests:

```bash
cd backend
pytest tests/test_database_routes.py -v
```

Test specific scenarios:

```bash
# Test connection creation
pytest tests/test_database_routes.py::TestDatabaseConnections::test_create_database_connection -v

# Test query execution
pytest tests/test_database_routes.py::TestDatabaseQueries::test_execute_natural_language_query -v

# Test history
pytest tests/test_database_routes.py::TestDatabaseQueries::test_get_query_history -v
```

## Frontend Integration

### React Component Example

```typescript
// useDatabase.ts - Custom hook for database queries
import { useState } from 'react';

interface QueryResult {
  queryId: string;
  generatedSql: string;
  result: any[];
  executionTimeMs: number;
}

export const useDatabase = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);

  const executeQuery = async (connectionId: string, naturalLanguageQuery: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/database/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          connection_id: connectionId,
          natural_language_query: naturalLanguageQuery
        })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return { executeQuery, loading, error, result };
};

// Usage in component
export const DatabaseQuery = () => {
  const { executeQuery, loading, result, error } = useDatabase();
  const [query, setQuery] = useState('');

  return (
    <div>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask a question about your data..."
      />
      <button
        onClick={() => executeQuery(selectedConnection, query)}
        disabled={loading}
      >
        {loading ? 'Executing...' : 'Execute Query'}
      </button>

      {result && (
        <div>
          <p>SQL: {result.generatedSql}</p>
          <p>Time: {result.executionTimeMs}ms</p>
          <table>
            {/* Render results */}
          </table>
        </div>
      )}

      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  );
};
```

## Limitations & Future Enhancements

### Current Limitations

- Only SELECT queries allowed
- Results limited to 1000 rows
- Passwords stored in plaintext (fix in production)
- No query caching

### Future Enhancements

1. **Query Caching**: Cache results for identical queries
2. **Custom Functions**: Support for custom SQL functions
3. **Advanced Analytics**: Built-in aggregations and visualizations
4. **Real-time Sync**: Auto-refresh data at intervals
5. **Query Templates**: Save frequently used queries
6. **Collaborative Queries**: Share queries between team members
7. **Query Optimization**: Suggest optimizations for slow queries
8. **Data Export**: Export results to CSV/Excel
9. **Scheduled Queries**: Run queries on schedule
10. **Webhooks**: Trigger webhooks on query results

## Troubleshooting

### Connection Issues

**Problem**: "Connection refused"

```
Solution: Check database host, port, and firewall rules
- Verify database is running
- Check network connectivity
- Ensure firewall allows connections
```

**Problem**: "Authentication failed"

```
Solution: Verify credentials
- Double-check username and password
- Ensure user has proper permissions
- Check for SSL certificate issues
```

### Query Issues

**Problem**: "Invalid SQL generated"

```
Solution: Provide more specific natural language query
- Use table and column names from schema
- Be more specific about what you want
- Check error message for hints
```

**Problem**: "Query timeout"

```
Solution: Reduce result size or optimize query
- Add more specific WHERE conditions
- Limit number of columns returned
- Use pagination for large datasets
```

## Support

For issues or feature requests:

1. Check the troubleshooting section above
2. Review test cases for usage examples
3. Contact the development team
4. Check application logs for detailed errors

## References

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MySQL Documentation](https://dev.mysql.com/doc/)
