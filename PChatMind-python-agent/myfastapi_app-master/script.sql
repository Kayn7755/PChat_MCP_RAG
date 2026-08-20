create table news_category
(
    id         int unsigned auto_increment comment '分类ID'
        primary key,
    name       varchar(50)                         not null comment '分类名称',
    sort_order int       default 0                 not null comment '排序顺序',
    created_at timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    updated_at timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint name_UNIQUE
        unique (name)
)
    comment '新闻分类表' charset = utf8mb4;

create table news
(
    id           int unsigned auto_increment comment '新闻ID'
        primary key,
    title        varchar(255)                           not null comment '新闻标题',
    description  varchar(500)                           null comment '新闻简介',
    content      text                                   not null comment '新闻内容',
    image        varchar(255)                           null comment '封面图片URL',
    author       varchar(50)                            null comment '作者',
    category_id  int unsigned                           not null comment '分类ID',
    views        int unsigned default '0'               not null comment '浏览量',
    publish_time timestamp    default CURRENT_TIMESTAMP not null comment '发布时间',
    created_at   timestamp    default CURRENT_TIMESTAMP not null comment '创建时间',
    updated_at   timestamp    default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint fk_news_category
        foreign key (category_id) references news_category (id)
            on update cascade
)
    comment '新闻表' charset = utf8mb4;

create index fk_news_category_idx
    on news (category_id);

create index idx_publish_time
    on news (publish_time desc);

create table related_news
(
    id              int unsigned auto_increment comment '关联ID'
        primary key,
    news_id         int unsigned                        not null comment '新闻ID',
    related_news_id int unsigned                        not null comment '相关新闻ID',
    created_at      timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    constraint news_related_unique
        unique (news_id, related_news_id),
    constraint fk_related_news_news
        foreign key (news_id) references news (id)
            on update cascade on delete cascade,
    constraint fk_related_news_related
        foreign key (related_news_id) references news (id)
            on update cascade on delete cascade
)
    comment '相关新闻关联表' charset = utf8mb4;

create index fk_related_news_news_idx
    on related_news (news_id);

create index fk_related_news_related_idx
    on related_news (related_news_id);

create table user
(
    id         int unsigned auto_increment comment '用户ID'
        primary key,
    username   varchar(50)                                                  not null comment '用户名',
    password   varchar(255)                                                 not null comment '密码（加密存储）',
    nickname   varchar(50)                                                  null comment '昵称',
    avatar     text                                                         null comment '头像URL（支持Base64）',
    gender     enum ('male', 'female', 'unknown') default 'unknown'         null comment '性别',
    bio        varchar(500)                                                 null comment '个人简介',
    phone      varchar(20)                                                  null comment '手机号',
    created_at timestamp                          default CURRENT_TIMESTAMP not null comment '创建时间',
    updated_at timestamp                          default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint phone_UNIQUE
        unique (phone),
    constraint username_UNIQUE
        unique (username)
)
    comment '用户信息表' charset = utf8mb4;

create table ai_chat
(
    id         int unsigned auto_increment comment '聊天记录ID'
        primary key,
    user_id    int unsigned                        not null comment '用户ID',
    message    text                                not null comment '用户消息',
    response   text                                not null comment 'AI回复',
    created_at timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    constraint fk_ai_chat_user
        foreign key (user_id) references user (id)
            on update cascade on delete cascade
)
    comment 'AI聊天记录表' charset = utf8mb4;

create index fk_ai_chat_user_idx
    on ai_chat (user_id);

create index idx_created_at
    on ai_chat (created_at desc);

create table favorite
(
    id         int unsigned auto_increment comment '收藏ID'
        primary key,
    user_id    int unsigned                        not null comment '用户ID',
    news_id    int unsigned                        not null comment '新闻ID',
    created_at timestamp default CURRENT_TIMESTAMP not null comment '收藏时间',
    constraint user_news_unique
        unique (user_id, news_id),
    constraint fk_favorite_news
        foreign key (news_id) references news (id)
            on update cascade on delete cascade,
    constraint fk_favorite_user
        foreign key (user_id) references user (id)
            on update cascade on delete cascade
)
    comment '收藏表' charset = utf8mb4;

create index fk_favorite_news_idx
    on favorite (news_id);

create index fk_favorite_user_idx
    on favorite (user_id);

create table history
(
    id        int unsigned auto_increment comment '历史ID'
        primary key,
    user_id   int unsigned                        not null comment '用户ID',
    news_id   int unsigned                        not null comment '新闻ID',
    view_time timestamp default CURRENT_TIMESTAMP not null comment '浏览时间',
    constraint fk_history_news
        foreign key (news_id) references news (id)
            on update cascade on delete cascade,
    constraint fk_history_user
        foreign key (user_id) references user (id)
            on update cascade on delete cascade
)
    comment '浏览历史表' charset = utf8mb4;

create index fk_history_news_idx
    on history (news_id);

create index fk_history_user_idx
    on history (user_id);

create index idx_view_time
    on history (view_time desc);

create table user_token
(
    id         int unsigned auto_increment comment '令牌ID'
        primary key,
    user_id    int unsigned                        not null comment '用户ID',
    token      varchar(255)                        not null comment '令牌值',
    expires_at timestamp                           not null comment '过期时间',
    created_at timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    updated_at datetime  default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint token_UNIQUE
        unique (token),
    constraint fk_user_token_user
        foreign key (user_id) references user (id)
            on update cascade on delete cascade
)
    comment '用户令牌表' charset = utf8mb4;

create index fk_user_token_user_idx
    on user_token (user_id);


