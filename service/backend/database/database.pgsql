create schema if not exists classification_reviews;

drop table if exists classification_reviews.users cascade;

create table if not exists classification_reviews.users (
    name VARCHAR(50),
    login VARCHAR(50) PRIMARY KEY,
    password bytea
);

INSERT INTO classification_reviews.users (name, login, password) VALUES 
('guest', 'guest', NULL);

drop table if exists classification_reviews.predicts;

create table if not exists classification_reviews.predicts (
    id serial PRiMARY KEY,
    owner VARCHAR(50) NOT NULL REFERENCES classification_reviews.users(login)
    ON DELETE cascade,
    used_model VARCHAR(50) NOT NULL,
    predict_date DATE NOT NULL
);

drop table if exists classification_reviews.models;

create table if not exists classification_reviews.models (
    id serial PRIMARY KEY,
    owner VARCHAR(50) NOT NULL REFERENCES classification_reviews.users(login)
    ON DELETE cascade,
    model_name VARCHAR(50) NOT NULL
);

