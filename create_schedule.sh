#!/bin/sh

cp com.roman.powerstrip.on.plist ~/Library/LaunchAgents/
cp com.roman.powerstrip.off.plist ~/Library/LaunchAgents/

launchctl load ~/Library/LaunchAgents/com.roman.powerstrip.on.plist
launchctl load ~/Library/LaunchAgents/com.roman.powerstrip.off.plist

launchctl list | grep com.roman.powerstrip
