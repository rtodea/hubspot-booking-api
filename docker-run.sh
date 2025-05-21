#!/usr/bin/env bash
docker pull roberttodea/hubspot-booking-api:latest

docker run \
  -p 8000:8000 \
  --rm \
  --env-file ./.env \
  --name hubspot-booking-api \
  roberttodea/hubspot-booking-api:latest
