import sqlite3

class Database:
    def __init__(self, db_name='database/clearml.db'):
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
                user_id INTEGER,
                experiment_id TEXT,
                section TEXT,
                metric_name TEXT,
                iteration INTEGER,
                value REAL,
                PRIMARY KEY (user_id, experiment_id, section, metric_name, iteration)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiments (
                user_id INTEGER,
                experiment_id TEXT,
                experiment_name TEXT,
                last_iteration INTEGER,
                text_msg_id INTEGER,
                train_msg_id INTEGER,
                val_msg_id INTEGER,
                PRIMARY KEY (user_id, experiment_id)
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

    def insert_metric(self, user_id, experiment_id, section, metric_name, iteration, value):
        self.cursor.execute('''
            INSERT or REPLACE INTO metrics (user_id, experiment_id, section, metric_name, iteration, value)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, experiment_id, section, metric_name, iteration, value))
        self.conn.commit()

    def get_metrics_by_section(self, experiment_id, section):
        self.cursor.execute('''
            SELECT * FROM metrics 
            WHERE experiment_id = ? AND section = ?
        ''', (experiment_id, section))
        return self.cursor.fetchall()
    
    def store_experiment_info(self, user_id, experiment_id, experiment_name, last_iteration, text_msg_id, train_msg_id, val_msg_id):
        self.cursor.execute('''
            INSERT OR REPLACE INTO experiments (user_id, experiment_id, experiment_name, last_iteration, text_msg_id, train_msg_id, val_msg_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, experiment_id, experiment_name, last_iteration, text_msg_id, train_msg_id, val_msg_id))
        self.conn.commit()

    def get_experiment_info(self, user_id, experiment_id):
        self.cursor.execute('SELECT * FROM experiments WHERE user_id = ? AND experiment_id = ?', 
                            (user_id, experiment_id))
        return self.cursor.fetchone()
    
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
