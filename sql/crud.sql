/*
 ^ Select One
 $ Select Value
 ! Insert/Update/Delete
 <! Insert/Update/Delete Returning
 *! Insert/Update/Delete Many
 # Execute Scripts
 */
-- name: create_schema#
create table trek (
    id serial primary key,
    origin text not null,
    owner_id int not null references user_(id),
    progress_at_hour smallint not null default 12 constraint hour_chk check (
        progress_at_hour >= 0
        and progress_at_hour <= 23
    ),
    progress_at_tz text not null default 'CET'
);


create table leg (
    id serial primary key,
    trek_id int references trek(id),
    destination text not null,
    added_at timestamp with time zone not null,
    added_by int references user_(id),
    is_ongoing boolean not null default false
);


/*add constraint added_by must be in trek_user for trek_id?*/
create unique index leg_unq_ix_trek_id_is_ongoing on leg (trek_id)
where
    is_ongoing;


create table waypoint (
    id serial primary key,
    trek_id smallint not null references trek(id),
    leg_id smallint not null references leg(id),
    lat double precision not null,
    lon double precision not null,
    elevation float,
    distance float not null
);


create index waypoint_ix_distance on waypoint (distance);


create table trek_user (
    trek_id int references trek(id),
    user_id int references user_(id),
    added_at timestamp with time zone not null
);


create unique index trek_user_unq_ix on trek_user (trek_id, user_id);


-- name: add_trek<!
insert into
    trek (origin, owner_id)
values
    (:origin, :owner_id) returning id;


-- name: add_leg<!
insert into
    leg (trek_id, destination, added_at, added_by)
values
    (:trek_id, :destination, :added_at, :added_by) returning id;


-- name: add_waypoints*!
insert into
    waypoint (trek_id, leg_id, lat, lon, distance, elevation)
values
    (
        :trek_id,
        :leg_id,
        :lat,
        :lon,
        :distance,
        :elevation
    );


-- name: add_trek_user
insert into
    trek_user (trek_id, user_id, added_at)
values
    (:trek_id, :user_id, :added_at);


-- name: prev_adder_id$
select
    added_by
from
    leg
where
    id = :leg_id
order by
    added_at desc
fetch first
    row only;


--name: next_adder_id$
/*https://itectec.com/database/postgresql-select-next-or-first-row/ */
/*next user*/
(
    select
        user_id
    from
        trek_user
    where
        trek_id = :trek_id
        and user_id > :prev_adder_id
    order by
        user_id
    fetch first
        row only
)
union
all
/*first user*/
(
    select
        user_id
    from
        trek_user
    where
        trek_id = :trek_id
    order by
        added_at
    fetch first
        row only
)
fetch first
    row only;


-- name: get_last_waypoint_for_leg^
select
    lat,
    lon,
    elevation
from
    waypoint
where
    leg_id = :leg_id
order by
    distance desc
fetch first
    row only;


-- name: start_leg!
update
    leg
set
    is_ongoing = true
where
    leg.id = :id;


-- name: get_trek^
select
    trek.origin,
    user_list.users as users
from
    trek
    cross join (
        select
            array_agg(user_id) as users
        from
            trek_user
        where
            trek_id = :trek_id
    ) as user_list
where
    trek.id = :trek_id;


-- name: get_legs_for_trek
select
    id,
    destination,
    added_at,
    is_ongoing
from
    leg
where
    trek_id = :trek_id
order by
    added_at;


-- name: get_treks_owner_of$
select
    array(
        select
            id
        from
            trek
        where
            owner_id = :user_id
    );


-- name: get_treks_user_in$
select
    array(
        select
            trek_id
        from
            trek_user
        where
            trek_user.user_id = :user_id
    );


-- name: delete_trek!
delete from
    waypoint
where
    trek_id = :trek_id;


delete from
    leg
where
    trek_id = :trek_id;


delete from
    trek_user
where
    trek_id = :trek_id;


delete from
    trek
where
    id = :trek_id;


-- name: is_trek_owner$
select
    exists(
        select
            1
        from
            trek
        where
            id = :trek_id
            and owner_id = :user_id
    );


-- name: is_trek_participant$
select
    exists(
        select
            1
        from
            trek_user
        where
            trek_id = :trek_id
            and user_id = :user_id
    );
