-- name: create_schema#
create table trek (
    id serial primary key,
    origin text not null
);


create table leg (
    id serial primary key,
    trek_id int references trek(id),
    destination text not null,
    added_at timestamp with time zone not null,
    is_ongoing boolean not null default false
);


--TODO: add constrain only ongoing leg per trek
create table waypoint (
    id serial primary key,
    trek_id smallint not null references trek(id),
    leg_id smallint not null references leg(id),
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
    trek (origin)
values
    (:origin) returning id;


-- name: add_leg<!
insert into
    leg (trek_id, destination, added_at)
values
    (:trek_id, :destination, :added_at) returning id;


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


-- name: add_trek_users*!
insert into
    trek_user (trek_id, user_id)
values
    (:trek_id, :user_id);


-- name: start_leg!
update
    leg
set
    is_ongoing = true
where
    leg.id = :id;


-- name: get_trek^
select
    trek.id,
    trek.origin,
    user_list.users as users,
    trek_leg.id as leg_id,
    trek_leg.destination as leg_destination,
    trek_leg.added_at as leg_added_at
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
    left join (
        select
            *
        from
            leg
        where
            leg.is_ongoing = true
            and leg.trek_id = :trek_id
    ) as trek_leg on trek_leg.id = trek.id
where
    trek.id = :trek_id;


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
