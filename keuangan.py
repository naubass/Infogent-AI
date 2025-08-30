import sqlite3

conn = sqlite3.connect("finance_dummy.db")
cursor = conn.cursor()

# Buat tabel accounts
cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY,
    account_name TEXT,
    balance REAL,
    currency TEXT
)
""")

# Buat tabel transactions
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY,
    account_id INTEGER,
    date TEXT,
    amount REAL,
    description TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
)
""")

# Insert data accounts
accounts_data = [
    (1, "Cash", 10000.00, "USD"),
    (2, "Savings Account", 25000.00, "USD"),
    (3, "Credit Card", -5000.00, "USD"),
]

cursor.executemany("INSERT INTO accounts VALUES (?, ?, ?, ?)", accounts_data)

# Insert data transactions
transactions_data = [
    (1, 1, "2025-08-01", -150.00, "Grocery shopping"),
    (2, 2, "2025-08-02", 2000.00, "Salary deposit"),
    (3, 3, "2025-08-03", -100.00, "Online subscription"),
    (4, 1, "2025-08-04", -200.00, "Utilities payment"),
    (5, 2, "2025-08-05", -500.00, "Car maintenance"),
]

cursor.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)", transactions_data)

conn.commit()
conn.close()

print("Database finance_dummy.db berhasil dibuat!")
