# Scratch Cookie Cottage — Admin app (Android)

A small Android app that opens the existing `/admin` portal. The public website no longer shows an Admin button. You can still open `/admin` in any browser.

## Install on your phone

This PC does not have Android Studio yet, so the app cannot be compiled here. One-time setup:

1. Install [Android Studio](https://developer.android.com/studio).
2. Open the folder `Documents\scratch-cookie-cottage\android-admin`.
3. Let it download the Android SDK when prompted.
4. Plug in your phone with **USB debugging** on (Settings → About phone → tap Build number 7 times, then enable USB debugging), **or** use an emulator.
5. Click the green **Run** button.

The app is installed only on that phone. It is not on the Play Store.

## First launch

Enter the website address (no `/admin` at the end).

| Where the site is running | Address to type |
|---|---|
| This computer, phone on the same Wi‑Fi | `http://192.168.1.249:5000` (your IP may change — `start.bat` prints the current one) |
| After the site is hosted | `https://www.scratchcookiecottage.com` |

Then log in with the same admin username and password as the website.

The three-dot menu has Refresh, Admin home, and Site address.

## Phone on home Wi‑Fi

1. Start the site with `start.bat` and leave that window open.
2. Phone and PC must be on the same Wi‑Fi.
3. Use the **Admin (phone Wi‑Fi)** URL that `start.bat` prints.

Windows may ask to allow Python through the firewall — choose **Private networks**.
