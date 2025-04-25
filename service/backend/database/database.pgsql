create schema if not exists classification_reviews;

drop table if exists classification_reviews.users;

create table if not exists classification_reviews.users (
    name VARCHAR(50),
    login VARCHAR(50) PRIMARY KEY,
    password bytea not null
);

drop table if exists classification_reviews.predicts;

create table if not exists classification_reviews.predicts (
    id serial PRiMARY KEY,
    owner VARCHAR(50) NOT NULL,
    used_model VARCHAR(50) NOT NULL,
    predict_date DATE NOT NULL
);