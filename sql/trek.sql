-- name: create_schema#
create table trek (
    id serial primary key,
    origin text not null,
    destination text not null,
    ongoing boolean not null,
    started_at date
);


create table waypoint (
    id serial primary key,
    trek_id smallint not null references trek(id),
    lat double precision not null,
    lon double precision not null,
    elevation float,
    distance float not null
);


create table trek_user (
    trek_id int references trek(id),
    user_id int references user_(id)
);


-- name: add_trek<!
insert into
    trek (origin, destination, ongoing)
values
    (:origin, :destination, false) returning id;


-- name: add_waypoints*!
insert into
    waypoint (trek_id, lat, lon, distance, elevation)
values
    (:trek_id, :lat, :lon, :distance, :elevation);


-- name: add_trek_users*!
insert into
    trek_user (trek_id, user_id)
values
    (:trek_id, :user_id);


-- name: get_trek^
select
    trek.id,
    trek.origin,
    trek.destination,
    trek.ongoing,
    trek.started_at,
    user_list.the_list as users
from
    trek
    cross join (
        select
            array_agg(user_id) as the_list
        from
            trek_user
        where
            trek_id = :trek_id
    ) as user_list
where
    id = :trek_id;


-- name: delete_trek!
delete from
    waypoint
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
