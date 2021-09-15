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
    id serial primary key,
    tracker_user_id text not null,
    is_admin boolean not null default false
);


--name: add_user<!
insert into
    user_ (tracker_user_id, is_admin)
values
    (:tracker_user_id, false) returning id as user_id;


-- name: user_for_user_id^
select
    id,
    tracker_user_id,
    is_admin
from
    user_
where
    id = :id;


-- name: user_id_for_tracker_user_id$
select
    id
from
    user_
where
    tracker_user_id = :tracker_user_id;


--name: get_all_users
select
    id,
    tracker_user_id,
    is_admin
from
    user_
