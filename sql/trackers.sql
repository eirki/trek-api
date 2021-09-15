-- name: create_schema#
create type tracker_type as enum ('fitbit', 'withings');


create table user_token (
  token json not null,
  user_id_ smallint not null references user_(id),
  tracker tracker_type not null
);


create unique index token_unq_ix_user_id_tracker on user_token (user_id_, tracker);


-- name: persist_token!
insert into
  user_token (token, user_id_, tracker)
values
  (:token, :user_id_, :tracker) on conflict (user_id_, tracker) do
update
set
  token = :token;
