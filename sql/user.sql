-- name: create_schema#
create table user_ (
    id serial primary key,
    name text not null,
    is_admin boolean not null default false
);
