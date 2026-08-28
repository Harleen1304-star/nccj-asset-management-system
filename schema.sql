CREATE TABLE IF NOT EXISTS users (

    user_id INTEGER PRIMARY KEY AUTOINCREMENT,

    username TEXT NOT NULL,

    email TEXT UNIQUE NOT NULL,

    password TEXT NOT NULL,

    role TEXT DEFAULT 'User',

    status TEXT DEFAULT 'Active'

);



CREATE TABLE IF NOT EXISTS user_requests (

    request_id INTEGER PRIMARY KEY AUTOINCREMENT,

    full_name TEXT,

    email TEXT,

    password TEXT,

    role TEXT DEFAULT 'User',

    status TEXT DEFAULT 'Pending',

    approved_by INTEGER

);



CREATE TABLE IF NOT EXISTS assets (

    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,

    asset_tag TEXT UNIQUE,

    asset_name TEXT,

    status TEXT DEFAULT 'Available',

    funder TEXT,

    last_audit_date DATE,

    next_audit_date DATE,

    due_checkin DATE

);



CREATE TABLE IF NOT EXISTS asset_assignments (

    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    asset_id INTEGER,

    assigned_date DATE,

    return_date DATE,

    status TEXT,

    FOREIGN KEY(user_id)
    REFERENCES users(user_id),

    FOREIGN KEY(asset_id)
    REFERENCES assets(asset_id)

);



CREATE TABLE IF NOT EXISTS asset_requests (

    request_id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    asset_id INTEGER,

    reason TEXT,

    status TEXT DEFAULT 'Pending',

    request_date DATE,

    approved_by INTEGER

);



CREATE TABLE IF NOT EXISTS asset_history (

    history_id INTEGER PRIMARY KEY AUTOINCREMENT,

    asset_id INTEGER,

    user_id INTEGER,

    action TEXT,

    action_date DATE,

    notes TEXT

);


CREATE TABLE IF NOT EXISTS notifications (

    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    request_id INTEGER NOT NULL,

    status TEXT NOT NULL,

    message TEXT NOT NULL,

    created_at DATETIME NOT NULL,

    is_read INTEGER DEFAULT 0,

    FOREIGN KEY(user_id)
    REFERENCES users(user_id),

    FOREIGN KEY(request_id)
    REFERENCES asset_requests(request_id)

);