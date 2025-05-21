#!/usr/bin/env bash
docker pull roberttodea/hubspot-booking-api:latest

docker run \
  -p 8080:8080 \
  --rm \
  --env-file ./.env \
  --name hubspot-booking-api \
  roberttodea/hubspot-booking-api:latest
