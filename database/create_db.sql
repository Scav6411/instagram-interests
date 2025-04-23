-- Create the users table
CREATE TABLE IF NOT EXISTS "user_data" (
    pk SERIAL PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255) DEFAULT '',
    profile_pic_url VARCHAR(255),
    profile_pic_url_hd VARCHAR(255),
    is_private BOOLEAN,
    
    CONSTRAINT unique_username UNIQUE (username)
);

-- Create the user_detail table
CREATE TABLE IF NOT EXISTS "user_detail" (
    pk INTEGER PRIMARY KEY,
    is_verified BOOLEAN DEFAULT FALSE,
    is_business BOOLEAN DEFAULT FALSE,
    biography TEXT DEFAULT '',
    follower_count INTEGER,
    following_count INTEGER,
    external_url VARCHAR(255),
    category_name VARCHAR(255),
    city_name VARCHAR(255),
    latitude FLOAT,
    longitude FLOAT,
    post_urls TEXT[],
    captions TEXT[],
    likes INTEGER[],
    posted_at DATE[],
    followers_list TEXT[],
    following_list TEXT[],
    interest_tags TEXT DEFAULT '',
    -- Add foreign key constraint to user table
    CONSTRAINT fk_user FOREIGN KEY (pk) REFERENCES "user_data" (pk) ON DELETE CASCADE
);

-- Create the follow_link table for the many-to-many relationship between users (followers/followees)
CREATE TABLE IF NOT EXISTS "follow_link" (
    follower_pk INTEGER,
    followee_pk INTEGER,
    PRIMARY KEY (follower_pk, followee_pk),
    CONSTRAINT fk_follower FOREIGN KEY (follower_pk) REFERENCES "user_data" (pk) ON DELETE CASCADE,
    CONSTRAINT fk_followee FOREIGN KEY (followee_pk) REFERENCES "user_data" (pk) ON DELETE CASCADE
);

-- Add mutual_follows table with username-based references
CREATE TABLE IF NOT EXISTS "mutual_follows" (
    follower_username TEXT NOT NULL,
    followee_username TEXT NOT NULL,
    PRIMARY KEY (follower_username, followee_username),
    CONSTRAINT fk_followee_username FOREIGN KEY (followee_username) 
        REFERENCES "user_data" (username)
);

-- Add unique constraint to username in user_data
ALTER TABLE "user_data" ADD CONSTRAINT unique_username UNIQUE (username);

-- Create function to find and insert mutual follows
CREATE OR REPLACE FUNCTION update_mutual_follows()
RETURNS TRIGGER AS $$
DECLARE
    username_val TEXT;
    mutual_username TEXT;
BEGIN
    -- Get the username for this user
    SELECT username INTO username_val
    FROM user_data
    WHERE pk = NEW.pk;
    
    -- Exit if we don't have a valid username
    IF username_val IS NULL THEN
        RETURN NEW;
    END IF;
    
    -- Delete existing mutual follows for this user to avoid duplicates
    DELETE FROM mutual_follows 
    WHERE followee_username = username_val;
    
    -- Find and insert mutual follows - usernames that appear in both followers and following lists
    -- The username_val is always the followee (the user we're checking mutuals for)
    FOR mutual_username IN 
        SELECT unnest(NEW.followers_list) AS username
        INTERSECT
        SELECT unnest(NEW.following_list) AS username
    LOOP
        INSERT INTO mutual_follows (follower_username, followee_username)
        VALUES (mutual_username, username_val);
    END LOOP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on user_detail table
CREATE TRIGGER update_mutual_follows_trigger
AFTER INSERT OR UPDATE OF followers_list, following_list
ON user_detail
FOR EACH ROW
EXECUTE FUNCTION update_mutual_follows();