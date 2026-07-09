# Deploy pipeline test

This file exists only to verify the Linux box's auto-pull-and-restart
systemd timer (`manufacture-autopull.timer`) correctly detects a new
commit on `main`, pulls it, runs its safety checks, and restarts
`manufacture.service`.

Safe to delete once verified.
