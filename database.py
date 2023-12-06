import sqlite3

class Database:
    def __init__(self, db_name='clearml.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                host TEXT,
                api_key TEXT,
                secret_key TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                experiment_name TEXT,
                section TEXT,
                metric_name TEXT,
                iteration INTEGER,
                value REAL,
                PRIMARY KEY (experiment_name, section, metric_name, iteration)
            )
        ''')

        self.conn.commit()

    def insert_user(self, user_id, username, host, api_key, secret_key):
        self.cursor.execute('''
            INSERT INTO users (user_id, username, host, api_key, secret_key)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, host, api_key, secret_key))
        self.conn.commit()

    def get_user_by_username(self, username):
        self.cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return self.cursor.fetchone()

    def get_user_by_id(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()

    def update_user_host(self, username, new_host):
        self.cursor.execute('UPDATE users SET host = ? WHERE username = ?', (new_host, username))
        self.conn.commit()

    def delete_user(self, username):
        self.cursor.execute('DELETE FROM users WHERE username = ?', (username,))
        self.conn.commit()

    def insert_metric(self, experiment_name, section, metric_name, iteration, value):
        self.cursor.execute('''
            INSERT or REPLACE INTO metrics (experiment_name, section, metric_name, iteration, value)
            VALUES (?, ?, ?, ?, ?)
        ''', (experiment_name, section, metric_name, iteration, value))
        self.conn.commit()

    def get_metrics_by_section(self, experiment_name, section):
        self.cursor.execute('''
            SELECT * FROM metrics 
            WHERE experiment_name = ? AND section = ?
        ''', (experiment_name, section))
        return self.cursor.fetchall()
    
    def close_connection(self):
        self.conn.close()

if __name__ == "__main__":
    db = Database()

    db.insert_user(1, 'example_user', 'example.com', 'api_key_123', 'secret_key_456')
    user_by_username = db.get_user_by_username('example_user')
    print("User by username:", user_by_username)

    db.update_user_host('example_user', 'newhost.com')

    user_by_id = db.get_user_by_id(1)
    print("User by user_id:", user_by_id)

    db.delete_user('example_user')
    db.close_connection()
