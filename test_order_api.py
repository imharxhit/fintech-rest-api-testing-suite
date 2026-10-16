import unittest
import sqlite3
import time
import jsonschema


ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "order_id": {"type": "string"},
        "account_id": {"type": "string"},
        "amount": {"type": "number", "minimum": 0},
        "status": {"type": "string", "enum": ["created", "processing", "completed", "cancelled"]},
        "timestamp": {"type": "number"}
    },
    "required": ["order_id", "account_id", "amount", "status", "timestamp"]
}


class MockOrderAPI:
    """Mock API server simulation for testing order endpoints with SQLite backing."""

    def __init__(self, db_conn):
        self.db = db_conn
        self.processed_idempotency_keys = set()
        self._init_db()

    def _init_db(self):
        cursor = self.db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                balance REAL NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                account_id TEXT,
                amount REAL,
                status TEXT
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO accounts VALUES ('ACC_123', 1000.00)")
        self.db.commit()

    def post_order(self, payload, headers):
        start_time = time.time()
        
        # Check idempotency key
        idem_key = headers.get("Idempotency-Key")
        if idem_key and idem_key in self.processed_idempotency_keys:
            latency = (time.time() - start_time) * 1000
            return 409, {"error": "Duplicate Idempotency-Key"}, latency

        if idem_key:
            self.processed_idempotency_keys.add(idem_key)

        # Validate request payload
        account_id = payload.get("account_id")
        amount = payload.get("amount", 0)

        cursor = self.db.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_id = ?", (account_id,))
        row = cursor.fetchone()

        if not row:
            latency = (time.time() - start_time) * 1000
            return 404, {"error": "Account not found"}, latency

        current_balance = row[0]
        if current_balance < amount:
            latency = (time.time() - start_time) * 1000
            return 400, {"error": "Insufficient funds"}, latency

        # Process order and update account balance
        new_balance = current_balance - amount
        cursor.execute("UPDATE accounts SET balance = ? WHERE account_id = ?", (new_balance, account_id))
        order_id = f"ORD_{int(time.time() * 1000)}"
        cursor.execute("INSERT INTO orders VALUES (?, ?, ?, ?)", (order_id, account_id, amount, "created"))
        self.db.commit()

        latency = (time.time() - start_time) * 1000
        response_data = {
            "order_id": order_id,
            "account_id": account_id,
            "amount": amount,
            "status": "created",
            "timestamp": time.time()
        }
        return 201, response_data, latency


class TestOrderAPI(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.api = MockOrderAPI(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_order_creation_contract_and_latency(self):
        """Verify POST /api/v1/orders JSON schema contract and response latency < 150ms."""
        payload = {"account_id": "ACC_123", "amount": 150.00}
        headers = {"Idempotency-Key": "key-001"}

        status_code, response, latency_ms = self.api.post_order(payload, headers)

        self.assertEqual(status_code, 201)
        self.assertLess(latency_ms, 150.0, f"Latency {latency_ms}ms exceeded 150ms limit")
        jsonschema.validate(instance=response, schema=ORDER_SCHEMA)

    def test_sqlite_account_balance_deduction(self):
        """Verify SQLite account balance is correctly debited after order placement."""
        initial_balance = 1000.00
        order_amount = 250.00

        payload = {"account_id": "ACC_123", "amount": order_amount}
        headers = {"Idempotency-Key": "key-002"}

        status_code, _, _ = self.api.post_order(payload, headers)
        self.assertEqual(status_code, 201)

        cursor = self.conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_id = ?", ("ACC_123",))
        updated_balance = cursor.fetchone()[0]

        self.assertEqual(updated_balance, initial_balance - order_amount)

    def test_duplicate_idempotency_key_rejection(self):
        """Verify 409 Conflict rejection on duplicate Idempotency-Key."""
        payload = {"account_id": "ACC_123", "amount": 50.00}
        headers = {"Idempotency-Key": "key-reuse-123"}

        status1, _, _ = self.api.post_order(payload, headers)
        self.assertEqual(status1, 201)

        status2, response2, _ = self.api.post_order(payload, headers)
        self.assertEqual(status2, 409)
        self.assertIn("error", response2)


if __name__ == "__main__":
    unittest.main()
