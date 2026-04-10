# Environment Setup Guide

## Start Redis

> The following commands need to be executed under `./data`

### Start Redis Docker Servers

```bash
cd data

# Redis for memo service
docker run -d \
  --name redis-memo \
  -p 6379:6379 \
  -v ./redis/data-6379:/data \
  redis:7

# Redis for task service
docker run -d \
  --name redis-task \
  -p 6380:6379 \
  -v ./redis/data-6380:/data \
  redis:7
```

### Clear Redis Data

```bash
# Clear redis-memo
docker exec -it redis-memo redis-cli
FLUSHALL
exit

# Clear redis-task
docker exec -it redis-task redis-cli
FLUSHALL
exit
```

```bash
# Remove local redis data
rm -rf ./redis/data-6379/*
rm -rf ./redis/data-6380/*

# Restart redis containers
docker restart redis-memo
docker restart redis-task
```

---

## Start MySQL

```bash
docker run -d \
  --name apix-mysql \
  -p 3307:3306 \
  -e MYSQL_ROOT_PASSWORD=22223333 \
  -e MYSQL_DATABASE=apix_database \
  -e MYSQL_USER=apix \
  -e MYSQL_PASSWORD=apixapix \
  --restart unless-stopped \
  mysql:8.0
```
