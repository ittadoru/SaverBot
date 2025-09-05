#!/bin/bash

docker build -t saver_bot .

docker compose up -d --build --force-recreate
