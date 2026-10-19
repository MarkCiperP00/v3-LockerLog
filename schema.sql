CREATE DATABASE IF NOT EXISTS lockerlog CHARACTER SET utf8mb4;
USE lockerlog;

CREATE TABLE users (
    school_id     VARCHAR(20)  PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'Student',
    CHECK (role IN ('Student','Professor/Staff','Maintenance','Administrator'))
) ENGINE=InnoDB;

CREATE TABLE lockers (
    locker_id VARCHAR(20) PRIMARY KEY,
    building  VARCHAR(10) NOT NULL,
    floor     INT         NOT NULL,
    status    VARCHAR(20) NOT NULL DEFAULT 'Available',
    CHECK (building IN ('COECSA','Sotero','JPL')),
    CHECK (status IN ('Available','Reserved','Assigned','Expired','Under Maintenance'))
) ENGINE=InnoDB;

-- one row per semester (2 per school year)
CREATE TABLE semesters (
    semester_id VARCHAR(20) PRIMARY KEY,      -- e.g. '2026-2027-1'
    school_year VARCHAR(9)  NOT NULL,         -- e.g. '2026-2027'
    term        TINYINT     NOT NULL,
    date_start  DATE        NOT NULL,
    date_end    DATE        NOT NULL,
    CHECK (term IN (1, 2)),
    CHECK (date_end > date_start),
    UNIQUE (school_year, term)
) ENGINE=InnoDB;

-- editable settings such as the daily rate ("key" is reserved in MySQL)
CREATE TABLE settings (
    setting_key   VARCHAR(50)  PRIMARY KEY,
    setting_value VARCHAR(100) NOT NULL
) ENGINE=InnoDB;
INSERT INTO settings VALUES ('rate_per_day', '5.00');

CREATE TABLE rental_requests (
    request_id     VARCHAR(20) PRIMARY KEY,
    school_id      VARCHAR(20) NOT NULL,
    locker_id      VARCHAR(20) NOT NULL,
    semester_id    VARCHAR(20) NOT NULL,
    date_submitted DATE        NOT NULL DEFAULT (CURRENT_DATE),
    status         VARCHAR(10) NOT NULL DEFAULT 'Pending',
    -- MySQL has no partial indexes: these are NULL unless the row is Pending
    pending_user   VARCHAR(20) GENERATED ALWAYS AS
                   (IF(status = 'Pending', school_id, NULL)) STORED,
    pending_locker VARCHAR(20) GENERATED ALWAYS AS
                   (IF(status = 'Pending', locker_id, NULL)) STORED,
    CHECK (status IN ('Pending','Approved','Rejected','Cancelled')),
    UNIQUE KEY one_pending_request_per_user   (pending_user),
    UNIQUE KEY one_pending_request_per_locker (pending_locker),
    FOREIGN KEY (school_id)   REFERENCES users(school_id),
    FOREIGN KEY (locker_id)   REFERENCES lockers(locker_id),
    FOREIGN KEY (semester_id) REFERENCES semesters(semester_id)
) ENGINE=InnoDB;

CREATE TABLE assignments (
    assignment_id VARCHAR(20)   PRIMARY KEY,
    request_id    VARCHAR(20)   NOT NULL UNIQUE,
    school_id     VARCHAR(20)   NOT NULL,
    locker_id     VARCHAR(20)   NOT NULL,
    semester_id   VARCHAR(20)   NOT NULL,
    date_start    DATE          NOT NULL,      -- set by system
    date_end      DATE          NOT NULL,      -- set by system (semester end)
    rate_per_day  DECIMAL(8,2)  NOT NULL,
    total_fee     DECIMAL(10,2) NOT NULL,
    status        VARCHAR(10)   NOT NULL DEFAULT 'Active',
    assigned_by   VARCHAR(20)   NOT NULL,
    -- NULL once the assignment is Released
    live_locker   VARCHAR(20)   GENERATED ALWAYS AS
                  (IF(status IN ('Active','Expired'), locker_id, NULL)) STORED,
    live_holder   VARCHAR(20)   GENERATED ALWAYS AS
                  (IF(status IN ('Active','Expired'), school_id, NULL)) STORED,
    CHECK (rate_per_day > 0),
    CHECK (total_fee >= 0),
    CHECK (date_end > date_start),
    CHECK (status IN ('Active','Expired','Released')),
    UNIQUE KEY one_active_assignment_per_locker (live_locker),
    UNIQUE KEY one_active_locker_per_holder     (live_holder),
    FOREIGN KEY (request_id)  REFERENCES rental_requests(request_id),
    FOREIGN KEY (school_id)   REFERENCES users(school_id),
    FOREIGN KEY (locker_id)   REFERENCES lockers(locker_id),
    FOREIGN KEY (semester_id) REFERENCES semesters(semester_id),
    FOREIGN KEY (assigned_by) REFERENCES users(school_id)
) ENGINE=InnoDB;

CREATE TABLE activity_log (
    log_id       INT AUTO_INCREMENT PRIMARY KEY,
    school_id    VARCHAR(20),
    action       VARCHAR(100) NOT NULL,
    locker_id    VARCHAR(20),
    rule_blocked VARCHAR(150),
    logged_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES users(school_id),
    FOREIGN KEY (locker_id) REFERENCES lockers(locker_id)
) ENGINE=InnoDB;
