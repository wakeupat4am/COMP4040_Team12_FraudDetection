ALTER TABLE users
ADD COLUMN clerk_user_id VARCHAR(255) NULL;

ALTER TABLE users
ALTER COLUMN password_hash DROP NOT NULL;

CREATE UNIQUE INDEX ix_users_clerk_user_id ON users(clerk_user_id);
