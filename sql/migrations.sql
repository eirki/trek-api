-- name: migrations#
create table user_ (
    id serial not null primary key,
    is_admin boolean not null default false
);


create table trek (
    id serial primary key,
    origin text not null,
    owner_id int not null references user_(id)
);


create table leg (
    id serial primary key,
    trek_id int references trek(id),
    destination text not null,
    added_at timestamp with time zone not null,
    is_ongoing boolean not null default false
);


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
    user_id int references user_(id)
);


create unique index trek_user_unq_ix on trek_user (trek_id, user_id);


create type tracker_type as enum ('fitbit', 'withings');


create table user_token (
    token json not null,
    user_id_ smallint not null references user_(id),
    tracker tracker_type not null,
    tracker_user_id text unique not null
);


create unique index token_unq_ix_user_id_tracker on user_token (user_id_, tracker);
