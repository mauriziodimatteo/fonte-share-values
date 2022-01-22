#!/bin/bash

gcloud functions deploy fonte-scraper \
--region europe-west1 \
--ignore-file .gcloudignore \
--runtime python37 \
--entry-point gcf_fonte_scraper \
--trigger-http \
--set-env-vars SHEET_KEY=1c5C-6Ir997is-bw84fqNfvU-AkJUYeC36zY6Sv23SXE \
--max-instances 1