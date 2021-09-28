/*
 ^ Select One
 $ Select Value
 ! Insert/Update/Delete
 <! Insert/Update/Delete Returning
 *! Insert/Update/Delete Many
 # Execute Scripts
 */
-- name: create_schema#
create table user_ (
    id serial not null primary key,
    is_admin boolean not null default false
);


--name: add_user<!
insert into
    user_ (is_admin)
values
    (:is_admin) returning id as user_id;


--name: get_all_users
select
    id,
    is_admin
from
    user_;
