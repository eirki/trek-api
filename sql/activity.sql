/*
 ^ Select One
 $ Select Value
 ! Insert/Update/Delete
 <! Insert/Update/Delete Returning
 *! Insert/Update/Delete Many
 # Execute Scripts
 */
-- name: create_schema#
create table step (
    trek_id smallint not null references trek(id),
    leg_id smallint not null references leg(id),
    user_id smallint not null references user_(id),
    taken_at date not null,
    amount integer not null
);


create unique index on step (trek_id, user_id, taken_at);


-- name: add_steps*!
insert into
    step (trek_id, leg_id, user_id, taken_at, amount)
values
    (
        :_id,
        :leg_id,
        :user_id,
        :taken_at,
        :amount
    );
