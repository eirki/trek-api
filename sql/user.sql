-- name: create_schema#
create table user_ (
    id serial primary key,
    name_ text not null,
    is_admin boolean not null default false
);


--name: add_user<!
insert into
    user_ (name_, is_admin)
values
    (:name, false) returning id as user_id;


-- name: get_user^
select
    id,
    name_ as name,
    is_admin
from
    user_
where
    id = :id;


--name: get_all_users
select
    id,
    name_ as name,
    is_admin
from
    user_
