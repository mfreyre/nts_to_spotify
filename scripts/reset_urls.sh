#!/bin/bash

# append the contents of the first file to the second file
cat urls.txt >> read_urls.txt

# move unread_csvs into read_csvs

mv ../unread_csvs/* ../read_csvss

# delete the contents of the first file
truncate -s 0 urls.txt
