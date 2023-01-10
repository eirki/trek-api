/*
 ^ Select One
 $ Select Value
 ! Insert/Update/Delete
 <! Insert/Update/Delete Returning
 *! Insert/Update/Delete Many
 # Execute Scripts
 */
-- name: create_schema#
create table location (
    trek_id smallint not null references trek(id),
    leg_id smallint not null references leg(id),
    visited_at date not null,
    /*latest_waypoint integer not null references waypoint(id),
     lat double precision not null,
     lon double precision not null,
     distance float not null,*/
    address text
    /*,country text,
     is_new_country boolean not null default false,
     poi text,
     photo_url text,
     map_img_url text,
     achievements text,
     factoid text*/
);


create index location_ix_date on location (visited_at);


--name: add_location!
insert into
    location (trek_id, leg_id, visited_at, address)
values
    (:trek_id, :leg_id, :visited_at, :address);


--name: most_recent_location
select
    *
from
    location
where
    trek_id = :trek_id
    and leg_id = :leg_id,
order by
    date desc
fetch first
    row only;


-- name: treks_to_update
with now as (
    select
        :now :: timestamp as tstamp
        /*Parameter :now must be in select, and must be first,
         if not it is converted to date below*/
),
trek_with_date as (
    select
        id,
        (
            :now :: date + interval '1 hour' * progress_at_hour
        ) at time zone progress_at_tz < now.tstamp as execute_yesterdays_progress
    from
        trek
        cross join now
),
ongoing_leg as (
    select
        *
    from
        leg
    where
        leg.is_ongoing = true
),
most_recent_location as (
    select
        distinct on (trek_id) trek_id,
        visited_at,
        :now :: date - location.visited_at as days_since_visit
    from
        location
    order by
        trek_id,
        visited_at desc
)
select
    trek.id as trek_id,
    trek.execute_yesterdays_progress,
    leg.id as leg_id,
    location.visited_at as most_recent_location_date
from
    trek_with_date as trek
    inner join ongoing_leg as leg on (leg.trek_id = trek.id)
    inner join most_recent_location as location on (location.trek_id = trek.id)
where
    (
        trek.execute_yesterdays_progress
        and location.days_since_visit > 1
    )
    or (location.days_since_visit > 2);
