#!/usr/bin/env bash

./docker-build.sh

docker tag hubspot-booking-api roberttodea/hubspot-booking-api:latest
docker push roberttodea/hubspot-booking-api:latest
