-- Run once as ADMIN in Database Actions > SQL on the Autonomous Database.
-- The app connects as this least-privilege user, never as ADMIN.
CREATE USER TRAVELDEAL IDENTIFIED BY "<choose-a-strong-password>";
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE TO TRAVELDEAL;
ALTER USER TRAVELDEAL QUOTA 2G ON DATA;
