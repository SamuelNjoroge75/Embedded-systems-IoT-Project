#pragma once

bool wifiConnect();                        // true if connected
bool timeIsValid();                        // true if the clock has been set
bool timeSync();                           // set the clock from NTP
bool mqttPublishData(const char* payload); // connect if needed, then publish
void networkShutdown();                    // clean disconnect (before sleep)
