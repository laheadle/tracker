
create table tuser (
       cid int primary key auto_increment
       ,cnickname varchar(150) not null unique
       ,cpassword varchar(150) not null
       ,cbaseBurn int not null
);

create table tactivity (
       cid int auto_increment primary key
       ,cname varchar(128)
       ,ccalories int not null
);

insert into tactivity (cid, cname, ccalories) values (1, 'Eat: Gain 1 Calorie', 1);
insert into tactivity (cid, cname, ccalories) values (2, 'Exercise: Burn 1 Calorie', -1);
insert into tactivity (cid, cname, ccalories) values (3, 'Base Burn: Burn Your Regular Calories', -1);

create table tchange (
       cid int auto_increment primary key
       ,cactivity int not null
       ,camount int not null
       ,cdate date not null
       ,cuser int not null 
       ,foreign key (cactivity) references tactivity (cid)
       ,foreign key (cuser) references tuser (cid)
);


