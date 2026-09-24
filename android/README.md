# Recovered Android project

The source in this directory came from the user's `android2.tar.gz` archive. Only source and Gradle configuration were copied; local machine settings, build caches, and the previously built APK were excluded.

`MainActivity` wraps `https://buildawallet.xyz/wallet` in an Android WebView. The web repository currently has no `/wallet` route, and the Android code does not create keys, apply a blueprint, sign transactions, or customize the APK for a user. Do not offer this as a working wallet download.

The `release` build type signs only when `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD` are provided. A Gradle wrapper and Android SDK are not bundled here. The source was inspected but cannot be compiled in this workspace, which has neither Gradle nor an Android SDK.

Next implementation milestone: create and verify an actual mobile wallet engine and safe configuration handoff, then add a reproducible signed build and delivery workflow. Keep private keys and signing credentials off the website and out of git.
