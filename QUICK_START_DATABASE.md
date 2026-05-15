# Quick Start Guide - Natural Language Database Queries

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Run Server

```bash
python -m uvicorn app.main:app --reload
```

### 3. Create Sample Connection

```bash
# First, get your auth token (see authentication endpoints)
curl -X POST http://localhost:8000/api/database/connections \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local PostgreSQL",
    "db_type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "database_name": "testdb",
    "username": "postgres",
    "password": "password",
    "ssl_enabled": false
  }'
```

### 4. Execute a Query

```bash
curl -X POST http://localhost:8000/api/database/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "YOUR_CONNECTION_ID",
    "natural_language_query": "How many users registered this week?"
  }'
```

## Common Use Cases

### Use Case 1: Sales Analytics

**Question**: "What were my top 5 products by revenue last month?"

```json
{
  "connection_id": "prod-db-id",
  "natural_language_query": "Show top 5 products by revenue from last month"
}
```

**Generated SQL**:

```sql
SELECT
    product_name,
    SUM(amount) as total_revenue,
    COUNT(*) as order_count
FROM orders
WHERE created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
  AND created_at < DATE_TRUNC('month', NOW())
GROUP BY product_name
ORDER BY total_revenue DESC
LIMIT 5
```

### Use Case 2: Customer Analysis

**Question**: "List all premium customers with more than $10k in orders"

```json
{
  "connection_id": "crm-db-id",
  "natural_language_query": "Show premium customers with total orders over 10000 dollars"
}
```

### Use Case 3: Performance Monitoring

**Question**: "Show me slow database queries from today"

```json
{
  "connection_id": "metrics-db-id",
  "natural_language_query": "Queries that took more than 1 second today"
}
```

## API Response Examples

### Successful Query

```json
{
  "query_id": "660e8400-e29b-41d4-a716-446655440001",
  "generated_sql": "SELECT * FROM users WHERE status = 'active' LIMIT 1000",
  "result": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "status": "active"
    },
    {
      "id": 2,
      "name": "Jane Smith",
      "email": "jane@example.com",
      "status": "active"
    }
  ],
  "execution_time_ms": 125
}
```

### Error Response

```json
{
  "detail": "Failed to connect to database: Connection refused"
}
```

## Connection Management

### List All Connections

```bash
curl -X GET http://localhost:8000/api/database/connections \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test Connection

```bash
curl -X POST http://localhost:8000/api/database/connections/CONNECTION_ID/test \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Delete Connection

```bash
curl -X DELETE http://localhost:8000/api/database/connections/CONNECTION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Supported Databases

| Database   | Driver    | Connection String                             |
| ---------- | --------- | --------------------------------------------- |
| PostgreSQL | asyncpg   | `postgresql+asyncpg://user:pass@host:port/db` |
| MySQL      | asyncmy   | `mysql+asyncmy://user:pass@host:port/db`      |
| SQLite     | aiosqlite | `sqlite+aiosqlite:///path/to/db.sqlite`       |

## Testing

### Run All Tests

```bash
cd backend
pytest tests/test_database_routes.py -v
```

### Test Connection Creation

```bash
pytest tests/test_database_routes.py::TestDatabaseConnections::test_create_database_connection -v
```

### Test Query Execution

```bash
pytest tests/test_database_routes.py::TestDatabaseQueries::test_execute_natural_language_query -v
```

## Environment Configuration

Add to `.env`:

```env
# Database Query Settings
MAX_QUERY_RESULTS=1000
QUERY_TIMEOUT_SECONDS=30

# LiteLLM Configuration (existing)
LITELLM_PROXY_URL=http://litellm.amzur.com:4000
LITELLM_VIRTUAL_KEY=your_key_here
LITELLM_MODEL=gemini-1.5-flash
```

## Code Examples

### Python Client

```python
import requests
import json

class DatabaseQueryClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def create_connection(self, name: str, db_type: str, host: str,
                         port: int, database_name: str, username: str,
                         password: str) -> dict:
        """Create a database connection."""
        data = {
            "name": name,
            "db_type": db_type,
            "host": host,
            "port": port,
            "database_name": database_name,
            "username": username,
            "password": password,
            "ssl_enabled": False
        }
        response = requests.post(
            f"{self.base_url}/api/database/connections",
            json=data,
            headers=self.headers
        )
        return response.json()

    def execute_query(self, connection_id: str, query: str) -> dict:
        """Execute a natural language query."""
        data = {
            "connection_id": connection_id,
            "natural_language_query": query
        }
        response = requests.post(
            f"{self.base_url}/api/database/query",
            json=data,
            headers=self.headers
        )
        return response.json()

    def get_connections(self) -> dict:
        """List all database connections."""
        response = requests.get(
            f"{self.base_url}/api/database/connections",
            headers=self.headers
        )
        return response.json()

# Usage
client = DatabaseQueryClient(
    "http://localhost:8000",
    token="your_auth_token"
)

# Create connection
conn = client.create_connection(
    name="My Database",
    db_type="postgresql",
    host="localhost",
    port=5432,
    database_name="myapp",
    username="postgres",
    password="password"
)

# Execute query
result = client.execute_query(
    connection_id=conn["id"],
    query="Show me all active users"
)

print(f"SQL: {result['generated_sql']}")
print(f"Results: {result['result']}")
print(f"Time: {result['execution_time_ms']}ms")
```

### TypeScript/React

```typescript
// databaseService.ts
interface DatabaseConnection {
  id: string;
  name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
}

interface QueryResult {
  query_id: string;
  generated_sql: string;
  result: Record<string, any>[];
  execution_time_ms: number;
}

export const databaseService = {
  async createConnection(
    connection: Omit<DatabaseConnection, 'id'>
  ): Promise<DatabaseConnection> {
    const response = await fetch('/api/database/connections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(connection),
    });
    return response.json();
  },

  async executeQuery(
    connectionId: string,
    query: string
  ): Promise<QueryResult> {
    const response = await fetch('/api/database/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        connection_id: connectionId,
        natural_language_query: query,
      }),
    });
    return response.json();
  },

  async listConnections(): Promise<DatabaseConnection[]> {
    const response = await fetch('/api/database/connections');
    const data = await response.json();
    return data.connections;
  },
};

// Usage in React
export const DatabaseQueryComponent = () => {
  const [connectionId, setConnectionId] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleExecute = async () => {
    setLoading(true);
    try {
      const result = await databaseService.executeQuery(connectionId, query);
      setResults(result);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask your question..."
      />
      <button onClick={handleExecute} disabled={loading}>
        {loading ? 'Executing...' : 'Execute'}
      </button>

      {results && (
        <div>
          <pre>{results.generated_sql}</pre>
          <table>
            <tbody>
              {results.result.map((row, idx) => (
                <tr key={idx}>
                  {Object.values(row).map((val, i) => (
                    <td key={i}>{String(val)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p>Executed in {results.execution_time_ms}ms</p>
        </div>
      )}
    </div>
  );
};
```

## Debugging Tips

### Check Generated SQL

Always review the generated SQL in the response to understand what query was generated.

### Enable Logging

Set DEBUG=True in your environment to see detailed logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Directly

Test your queries directly in your database client first, then ask the same question in natural language.

### Schema Information

Verify the schema_info in your connection to ensure all tables/columns are included:

```bash
curl http://localhost:8000/api/database/connections/CONNECTION_ID \
  -H "Authorization: Bearer TOKEN" | jq '.schema_info'
```

## Performance Tips

1. **Be Specific**: More specific queries execute faster
2. **Use Filters**: Add WHERE conditions to reduce result set
3. **Limit Results**: Results are automatically limited to 1000 rows
4. **Use Indexes**: Ensure database has proper indexes
5. **Cache Results**: Reuse results for identical queries

## Limits & Quotas

| Item                   | Limit               |
| ---------------------- | ------------------- |
| Query Results          | 1000 rows per query |
| Query Timeout          | 30 seconds          |
| Max Connections        | Unlimited per user  |
| Query History          | All queries stored  |
| Connection Credentials | Per-user storage    |

## Getting Help

- Check `DATABASE_QUERIES.md` for full documentation
- Review `backend/tests/test_database_routes.py` for usage examples
- Check application logs for error details
- Review schema information to understand available data

## Next Steps

1. ✅ Set up your first database connection
2. ✅ Test a simple query
3. ✅ Review the full documentation
4. ✅ Integrate into your frontend
5. ✅ Set up monitoring and logging
