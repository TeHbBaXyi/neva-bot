-- Схема PostgreSQL для прода (локально таблицы создаёт init_db из моделей).
CREATE TABLE groups (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(64)  NOT NULL,
    day_of_week   VARCHAR(16)  NOT NULL,
    starts_at     TIME         NOT NULL,
    duration_min  INTEGER      NOT NULL,
    price         INTEGER      NOT NULL,
    level         VARCHAR(64)  NOT NULL,
    topic         VARCHAR(255) NOT NULL,
    description   VARCHAR(1000) NOT NULL,
    capacity      INTEGER      NOT NULL DEFAULT 8
);

CREATE TABLE bookings (
    id         SERIAL PRIMARY KEY,
    group_id   INTEGER     NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    name       VARCHAR(128) NOT NULL,
    phone      VARCHAR(32)  NOT NULL,
    status     VARCHAR(16)  NOT NULL DEFAULT 'new',
    created_at TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX idx_bookings_group ON bookings(group_id);
