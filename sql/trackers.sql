-- name: create_schema#
create type tracker_type as enum ('fitbit', 'withings');


create table user_token (
  token json not null,
  user_id_ smallint not null references user_(id),
  tracker tracker_type not null,
  tracker_user_id text unique not null
);


create unique index token_unq_ix_user_id_tracker on user_token (user_id_, tracker);


-- name: persist_token!
insert into
  user_token (token, user_id_, tracker, tracker_user_id)
values
  (:token, :user_id_, :tracker, :tracker_user_id) on conflict (user_id_, tracker) do
update
set
  token = :token,
  tracker_user_id = :tracker_user_id;


-- name: user_id_for_tracker_user_id$
select
  user_id_
from
  user_token
where
  tracker_user_id = :tracker_user_id;


--name: tokens_for_user
select
  user_id_,
  token,
  tracker
from
  user_token
where
  user_id_ = :user_id
