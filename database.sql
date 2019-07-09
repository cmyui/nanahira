create database tohru;
use tohru;
create schema tohru collate latin1_swedish_ci;

create table uploads
(
	id int auto_increment,
	user int not null,
	filename varchar(64) not null,
	filesize int not null,
	time int not null,
	constraint uploads_filename_uindex
		unique (filename),
	constraint uploads_id_uindex
		unique (id)
);

alter table uploads
	add primary key (id);

create table users
(
	id int auto_increment
		primary key,
	username varchar(32) not null,
	token varchar(128) not null,
	constraint users_token_uindex
		unique (token),
	constraint users_username_uindex
		unique (username)
);

