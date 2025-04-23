create schema if not exists classification_reviews;

drop table if exists classification_reviews.users;

create table if not exists classification_reviews.users (
    name varchar(50),
    login varchar(50) PRIMARY KEY,
    password bytea not null
);

drop table if exists classification_reviews.predicts;

create table if not exists classification_reviews.predicts (
    id serial PRiMARY KEY,
    owner varchar(50) NOT NULL,
    used_model varchar(50) NOT NULL
);