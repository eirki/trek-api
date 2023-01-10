-- name: migrations#
create type "public"."tracker_type" as enum ('fitbit', 'withings');


create sequence "public"."leg_id_seq";


create sequence "public"."trek_id_seq";


create sequence "public"."user__id_seq";


create sequence "public"."waypoint_id_seq";


create table "public"."leg" (
    "id" integer not null default nextval('leg_id_seq' :: regclass),
    "trek_id" integer,
    "destination" text not null,
    "added_at" timestamp with time zone not null,
    "added_by" integer,
    "is_ongoing" boolean not null default false
);


create table "public"."trek" (
    "id" integer not null default nextval('trek_id_seq' :: regclass),
    "origin" text not null,
    "owner_id" integer not null,
    "progress_at_hour" smallint not null default 12,
    "progress_at_tz" text not null default 'CET' :: text
);


create table "public"."trek_user" (
    "trek_id" integer,
    "user_id" integer,
    "added_at" timestamp with time zone not null
);


create table "public"."user_" (
    "id" integer not null default nextval('user__id_seq' :: regclass),
    "is_admin" boolean not null default false
);


create table "public"."user_token" (
    "token" text not null,
    "user_id_" smallint not null,
    "tracker" tracker_type not null,
    "tracker_user_id" text not null
);


create table "public"."waypoint" (
    "id" integer not null default nextval('waypoint_id_seq' :: regclass),
    "trek_id" smallint not null,
    "leg_id" smallint not null,
    "lat" double precision not null,
    "lon" double precision not null,
    "elevation" double precision,
    "distance" double precision not null
);


alter sequence "public"."leg_id_seq" owned by "public"."leg"."id";


alter sequence "public"."trek_id_seq" owned by "public"."trek"."id";


alter sequence "public"."user__id_seq" owned by "public"."user_"."id";


alter sequence "public"."waypoint_id_seq" owned by "public"."waypoint"."id";


CREATE UNIQUE INDEX leg_pkey ON public.leg USING btree (id);


CREATE UNIQUE INDEX leg_unq_ix_trek_id_is_ongoing ON public.leg USING btree (trek_id)
WHERE
    is_ongoing;


CREATE UNIQUE INDEX token_unq_ix_user_id_tracker ON public.user_token USING btree (user_id_, tracker);


CREATE UNIQUE INDEX trek_pkey ON public.trek USING btree (id);


CREATE UNIQUE INDEX trek_user_unq_ix ON public.trek_user USING btree (trek_id, user_id);


CREATE UNIQUE INDEX user__pkey ON public.user_ USING btree (id);


CREATE UNIQUE INDEX user_token_tracker_user_id_key ON public.user_token USING btree (tracker_user_id);


CREATE INDEX waypoint_ix_distance ON public.waypoint USING btree (distance);


CREATE UNIQUE INDEX waypoint_pkey ON public.waypoint USING btree (id);


alter table
    "public"."leg"
add
    constraint "leg_pkey" PRIMARY KEY using index "leg_pkey";


alter table
    "public"."trek"
add
    constraint "trek_pkey" PRIMARY KEY using index "trek_pkey";


alter table
    "public"."user_"
add
    constraint "user__pkey" PRIMARY KEY using index "user__pkey";


alter table
    "public"."waypoint"
add
    constraint "waypoint_pkey" PRIMARY KEY using index "waypoint_pkey";


alter table
    "public"."leg"
add
    constraint "leg_added_by_fkey" FOREIGN KEY (added_by) REFERENCES user_(id);


alter table
    "public"."leg"
add
    constraint "leg_trek_id_fkey" FOREIGN KEY (trek_id) REFERENCES trek(id);


alter table
    "public"."trek"
add
    constraint "hour_chk" CHECK (
        (
            (progress_at_hour >= 0)
            AND (progress_at_hour <= 23)
        )
    );


alter table
    "public"."trek"
add
    constraint "trek_owner_id_fkey" FOREIGN KEY (owner_id) REFERENCES user_(id);


alter table
    "public"."trek_user"
add
    constraint "trek_user_trek_id_fkey" FOREIGN KEY (trek_id) REFERENCES trek(id);


alter table
    "public"."trek_user"
add
    constraint "trek_user_user_id_fkey" FOREIGN KEY (user_id) REFERENCES user_(id);


alter table
    "public"."user_token"
add
    constraint "user_token_tracker_user_id_key" UNIQUE using index "user_token_tracker_user_id_key";


alter table
    "public"."user_token"
add
    constraint "user_token_user_id__fkey" FOREIGN KEY (user_id_) REFERENCES user_(id);


alter table
    "public"."waypoint"
add
    constraint "waypoint_leg_id_fkey" FOREIGN KEY (leg_id) REFERENCES leg(id);


alter table
    "public"."waypoint"
add
    constraint "waypoint_trek_id_fkey" FOREIGN KEY (trek_id) REFERENCES trek(id);
