-- name: migrations#
alter table
    user_token
alter column
    token
set
    data type text using token :: text;
