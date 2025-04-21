create schema if not exists classification_review;

drop table if exists classification_review.users;

create table if not exists classification_review.users (
    id serial PRIMARY KEY,
    name varchar(50),
    login varchar(50) not null,
    password bytea not null
);